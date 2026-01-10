"""Unit tests for klipper-docs-mcp server."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from klipper_docs_mcp.config import MAX_FILE_CHARS
from klipper_docs_mcp import server
from klipper_docs_mcp.services import GitManager, SearchEngine, StorageManager


@pytest.fixture
def temp_docs_dir():
    """Create a temporary documentation directory structure with multi-repo support."""
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_path = Path(tmpdir) / "docs"
        docs_path.mkdir()

        # Create Klipper repo
        klipper_path = docs_path / "klipper"
        klipper_path.mkdir()
        (klipper_path / "README.md").write_text("# Klipper Documentation\n\nWelcome to Klipper.")
        (klipper_path / "Config_Reference.md").write_text(
            "# Config Reference\n\n"
            "This section describes configuration options.\n"
            "## Stepper Configuration\n\n"
            "stepper_x:\n"
            "  step_pin: P1.20"
        )
        (klipper_path / "prints").mkdir()
        (klipper_path / "prints" / "bed_mesh.md").write_text(
            "# Bed Mesh\n\n"
            "Bed leveling with mesh calibration.\n"
            "Run BED_MESH_CALIBRATE to start."
        )

        # Create Moonraker repo
        moonraker_path = docs_path / "moonraker"
        moonraker_path.mkdir()
        (moonraker_path / "api.md").write_text("# Moonraker API\n\nHTTP API endpoints.")

        # Create new services with temp directory
        storage_manager = StorageManager()
        storage_manager.config.docs_dir = docs_path

        git_manager = GitManager()
        git_manager.config.docs_dir = docs_path

        search_engine = SearchEngine(docs_dir=docs_path)

        # Patch server module's global services
        with patch.object(server, "_storage_manager", storage_manager), \
             patch.object(server, "_git_manager", git_manager), \
             patch.object(server, "_search_engine", search_engine):
            yield docs_path


class TestSearchDocs:
    """Tests for search_docs function."""

    @pytest.mark.asyncio
    async def test_search_finds_filename_match(self, temp_docs_dir):
        """Test that search finds matches in filenames."""
        results = await server.search_docs("config")
        content = results[0].text

        assert "klipper/Config_Reference.md" in content
        assert "Config Reference" in content

    @pytest.mark.asyncio
    async def test_search_finds_heading_match(self, temp_docs_dir):
        """Test that search finds matches in markdown headings."""
        results = await server.search_docs("bed mesh")
        content = results[0].text

        assert "klipper/prints/bed_mesh.md" in content
        assert "Bed Mesh" in content

    @pytest.mark.asyncio
    async def test_search_finds_content_match(self, temp_docs_dir):
        """Test that search finds matches in file content."""
        results = await server.search_docs("stepper")
        content = results[0].text

        assert "klipper/Config_Reference.md" in content
        assert "stepper_x:" in content or "Stepper" in content

    @pytest.mark.asyncio
    async def test_search_cross_repo(self, temp_docs_dir):
        """Test search across multiple repositories."""
        # Search for something in Moonraker
        results = await server.search_docs("api")
        content = results[0].text
        assert "moonraker/api.md" in content
        assert "Moonraker API" in content

    @pytest.mark.asyncio
    async def test_search_respects_max_results(self, temp_docs_dir):
        """Test that search returns at most MAX_SEARCH_RESULTS."""
        # Create many files in Klipper repo
        klipper_path = temp_docs_dir / "klipper"
        for i in range(15):
            (klipper_path / f"test_{i}.md").write_text(f"Content {i}")

        results = await server.search_docs("test")
        # Should return max 7 results
        assert len(results[0].text.split("## ")) - 1 <= 7

    @pytest.mark.asyncio
    async def test_search_deduplication(self, temp_docs_dir):
        """Test that search doesn't return duplicate matches for headings."""
        # Create a file where query is in heading
        (temp_docs_dir / "klipper" / "dedup.md").write_text("# Unique Heading Test\n\nSome content.")

        results = await server.search_docs("Unique Heading")
        content = results[0].text

        # Should find the heading
        assert "Unique Heading" in content


class TestReadDoc:
    """Tests for read_doc function."""

    @pytest.mark.asyncio
    async def test_read_doc_valid_path(self, temp_docs_dir):
        """Test reading a valid documentation file."""
        results = await server.read_doc("klipper/README.md")
        content = results[0].text

        assert "Klipper Documentation" in content
        assert "Welcome to Klipper" in content

    @pytest.mark.asyncio
    async def test_read_doc_nested_path(self, temp_docs_dir):
        """Test reading a file in a subdirectory."""
        results = await server.read_doc("klipper/prints/bed_mesh.md")
        content = results[0].text

        assert "Bed Mesh" in content
        assert "BED_MESH_CALIBRATE" in content

    @pytest.mark.asyncio
    async def test_read_doc_truncates_large_files(self, temp_docs_dir):
        """Test that large files are truncated to MAX_FILE_CHARS."""
        # Create a file larger than MAX_FILE_CHARS
        large_content = "x" * (MAX_FILE_CHARS + 5000)
        (temp_docs_dir / "klipper" / "large.md").write_text(large_content)

        results = await server.read_doc("klipper/large.md")
        content = results[0].text

        assert len(content) <= MAX_FILE_CHARS + 200  # Allow for truncation message
        assert "Showing characters" in content

    @pytest.mark.asyncio
    async def test_read_doc_path_traversal_protection(self, temp_docs_dir):
        """Test that path traversal attempts are blocked."""
        results = await server.read_doc("../../../etc/passwd")
        content = results[0].text

        assert "Access denied" in content or "invalid path" in content.lower()

    @pytest.mark.asyncio
    async def test_read_doc_nonexistent_file(self, temp_docs_dir):
        """Test reading a file that doesn't exist."""
        results = await server.read_doc("klipper/nonexistent.md")
        content = results[0].text

        assert "not found" in content.lower()

    @pytest.mark.asyncio
    async def test_read_doc_pagination(self, temp_docs_dir):
        """Test reading a file with offset and limit."""
        content_str = "0123456789" * 10  # 100 chars
        (temp_docs_dir / "klipper" / "numbers.txt").write_text(content_str)

        # Test offset
        results = await server.read_doc("klipper/numbers.txt", offset=10, limit=20)
        content = results[0].text
        assert content.startswith("0123456789")
        assert len(content.split("\n\n")[0]) == 20
        assert "Showing characters 10-30" in content


class TestListDocsMap:
    """Tests for list_docs_map function."""

    @pytest.mark.asyncio
    async def test_list_docs_map_structure(self, temp_docs_dir):
        """Test that docs map shows directory structure including repos."""
        results = await server.list_docs_map()
        content = results[0].text

        assert "klipper/" in content
        assert "moonraker/" in content
        assert "README.md" in content
        assert "Config_Reference.md" in content


class TestGitManager:
    """Tests for GitManager functionality."""

    @pytest.mark.asyncio
    async def test_check_outdated_nonexistent_dir(self):
        """Test check returns False when docs dir doesn't exist."""
        git_manager = GitManager()
        git_manager.config.docs_dir = Path("/nonexistent/path")
        result = git_manager.check_if_outdated()
        assert result is False