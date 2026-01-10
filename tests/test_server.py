"""Unit tests for klipper-docs-mcp server."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from klipper_docs_mcp.server import (
    MAX_FILE_CHARS,
    DOCS_DIR,
    list_docs_map,
    read_doc,
    search_docs,
    check_if_outdated,
)


@pytest.fixture
def temp_docs_dir():
    """Create a temporary documentation directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_path = Path(tmpdir) / "docs"
        docs_path.mkdir()

        # Create test files
        (docs_path / "README.md").write_text("# Klipper Documentation\n\nWelcome to Klipper.")
        (docs_path / "Config_Reference.md").write_text(
            "# Config Reference\n\n"
            "This section describes configuration options.\n"
            "## Stepper Configuration\n\n"
            "stepper_x:\n"
            "  step_pin: P1.20"
        )
        (docs_path / "prints").mkdir()
        (docs_path / "prints" / "bed_mesh.md").write_text(
            "# Bed Mesh\n\n"
            "Bed leveling with mesh calibration.\n"
            "Run BED_MESH_CALIBRATE to start."
        )

        # Patch DOCS_DIR
        with patch("klipper_docs_mcp.server.DOCS_DIR", docs_path):
            yield docs_path


class TestSearchDocs:
    """Tests for search_docs function."""

    @pytest.mark.asyncio
    async def test_search_finds_filename_match(self, temp_docs_dir):
        """Test that search finds matches in filenames."""
        results = await search_docs("config")
        content = results[0].text

        assert "Config_Reference.md" in content
        assert "Config Reference" in content

    @pytest.mark.asyncio
    async def test_search_finds_heading_match(self, temp_docs_dir):
        """Test that search finds matches in markdown headings."""
        results = await search_docs("bed mesh")
        content = results[0].text

        assert "bed_mesh.md" in content
        assert "Bed Mesh" in content

    @pytest.mark.asyncio
    async def test_search_finds_content_match(self, temp_docs_dir):
        """Test that search finds matches in file content."""
        results = await search_docs("stepper")
        content = results[0].text

        assert "Config_Reference.md" in content
        assert "stepper_x:" in content or "Stepper" in content

    @pytest.mark.asyncio
    async def test_search_respects_max_results(self, temp_docs_dir):
        """Test that search returns at most MAX_SEARCH_RESULTS."""
        # Create many files
        for i in range(15):
            (temp_docs_dir / f"test_{i}.md").write_text(f"Content {i}")

        results = await search_docs("test")
        # Should return max 7 results
        assert len(results[0].text.split("## ")) - 1 <= 7


class TestReadDoc:
    """Tests for read_doc function."""

    @pytest.mark.asyncio
    async def test_read_doc_valid_path(self, temp_docs_dir):
        """Test reading a valid documentation file."""
        results = await read_doc("README.md")
        content = results[0].text

        assert "Klipper Documentation" in content
        assert "Welcome to Klipper" in content

    @pytest.mark.asyncio
    async def test_read_doc_nested_path(self, temp_docs_dir):
        """Test reading a file in a subdirectory."""
        results = await read_doc("prints/bed_mesh.md")
        content = results[0].text

        assert "Bed Mesh" in content
        assert "BED_MESH_CALIBRATE" in content

    @pytest.mark.asyncio
    async def test_read_doc_truncates_large_files(self, temp_docs_dir):
        """Test that large files are truncated to MAX_FILE_CHARS."""
        # Create a file larger than MAX_FILE_CHARS
        large_content = "x" * (MAX_FILE_CHARS + 5000)
        (temp_docs_dir / "large.md").write_text(large_content)

        results = await read_doc("large.md")
        content = results[0].text

        assert len(content) <= MAX_FILE_CHARS + 200  # Allow for truncation message
        assert "Showing characters" in content

    @pytest.mark.asyncio
    async def test_read_doc_path_traversal_protection(self, temp_docs_dir):
        """Test that path traversal attempts are blocked."""
        results = await read_doc("../../../etc/passwd")
        content = results[0].text

        assert "Access denied" in content or "invalid path" in content.lower()

    @pytest.mark.asyncio
    async def test_read_doc_nonexistent_file(self, temp_docs_dir):
        """Test reading a file that doesn't exist."""
        results = await read_doc("nonexistent.md")
        content = results[0].text

        assert "not found" in content.lower()

    @pytest.mark.asyncio
    async def test_read_doc_pagination(self, temp_docs_dir):
        """Test reading a file with offset and limit."""
        content_str = "0123456789" * 10  # 100 chars
        (temp_docs_dir / "numbers.txt").write_text(content_str)

        # Test offset
        results = await read_doc("numbers.txt", offset=10, limit=20)
        content = results[0].text
        assert content.startswith("0123456789")
        assert len(content.split("\n\n")[0]) == 20
        assert "Showing characters 10-30" in content

        # Test limit
        results = await read_doc("numbers.txt", offset=0, limit=5)
        content = results[0].text
        assert content.startswith("01234")
        assert len(content.split("\n\n")[0]) == 5



class TestListDocsMap:
    """Tests for list_docs_map function."""

    @pytest.mark.asyncio
    async def test_list_docs_map_structure(self, temp_docs_dir):
        """Test that docs map shows directory structure."""
        results = await list_docs_map()
        content = results[0].text

        assert "README.md" in content
        assert "Config_Reference.md" in content
        assert "prints/" in content
        assert "bed_mesh.md" in content


class TestCheckIfOutdated:
    """Tests for check_if_outdated function."""

    @pytest.mark.asyncio
    async def test_check_outdated_nonexistent_dir(self):
        """Test check returns False when docs dir doesn't exist."""
        with patch("klipper_docs_mcp.server.DOCS_DIR", Path("/nonexistent/path")):
            result = await check_if_outdated()
            assert result is False
