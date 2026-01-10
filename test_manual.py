"""Manual tests for server logic without MCP SDK."""

import os
import tempfile
from pathlib import Path


def test_search_logic():
    """Test search algorithm without MCP."""
    import re

    # Create temp docs structure
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_path = Path(tmpdir) / "docs"
        docs_path.mkdir()

        # Create test files
        (docs_path / "README.md").write_text("# Klipper\n\nWelcome to Klipper 3D printer firmware.")
        (docs_path / "Config_Reference.md").write_text(
            "# Config Reference\n\n"
            "stepper_x:\n"
            "  step_pin: P1.20"
        )
        (docs_path / "prints").mkdir()
        (docs_path / "prints" / "bed_mesh.md").write_text(
            "# Bed Mesh\n\n"
            "Run BED_MESH_CALIBRATE to start."
        )

        # Test 1: Search by filename
        query = "config"
        results = []

        for root, dirs, files in os.walk(docs_path):
            for file in files:
                if file.endswith((".md", ".txt")):
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(docs_path)

                    with open(file_path, "r") as f:
                        content = f.read()

                    # Filename match (highest priority)
                    if query.lower() in str(rel_path).lower():
                        results.append((1, str(rel_path), "filename match"))

                    # Heading match
                    heading_match = re.search(r"^#+.*" + re.escape(query) + ".*$", content, re.MULTILINE | re.IGNORECASE)
                    if heading_match:
                        results.append((2, str(rel_path), "heading match"))

                    # Content match
                    if query.lower() in content.lower():
                        results.append((3, str(rel_path), "content match"))

        results.sort(key=lambda x: x[0])

        print("=== Test 1: Search by filename ===")
        for rank, path, reason in results[:3]:
            print(f"  Rank {rank}: {path} ({reason})")
        assert any("Config_Reference.md" in r[1] for r in results), "Should find Config_Reference.md"
        print("  ✓ PASSED\n")


def test_read_doc_logic():
    """Test read_doc security and truncation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_path = Path(tmpdir) / "docs"
        docs_path.mkdir()

        (docs_path / "test.md").write_text("x" * 15000)  # Large file
        (docs_path / "safe.md").write_text("Safe content")

        # Test 1: Truncation
        with open(docs_path / "test.md") as f:
            content = f.read()

        MAX_FILE_CHARS = 10000
        if len(content) > MAX_FILE_CHARS:
            content = content[:MAX_FILE_CHARS] + f"\n\n[... truncated]"

        print("=== Test 2: File truncation ===")
        print(f"  Original: 15000 chars")
        print(f"  After: {len(content)} chars")
        assert len(content) <= MAX_FILE_CHARS + 200, "Should be truncated"
        assert "truncated" in content.lower(), "Should have truncation marker"
        print("  ✓ PASSED\n")

        # Test 2: Path traversal protection
        print("=== Test 3: Path traversal protection ===")
        try:
            target_path = (docs_path / "../../../etc/passwd").resolve()
            common = os.path.commonpath([docs_path, target_path])
            if common != str(docs_path):
                raise ValueError("Path traversal blocked")
        except ValueError as e:
            print(f"  ✓ Path traversal blocked: {e}\n")


def test_tree_structure():
    """Test docs tree generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_path = Path(tmpdir) / "docs"
        docs_path.mkdir()

        (docs_path / "README.md").write_text("# Readme")
        (docs_path / "config").mkdir()
        (docs_path / "config" / "printer.md").write_text("# Printer Config")
        (docs_path / "config" / "steppers").mkdir()
        (docs_path / "config" / "steppers" / "stepper_x.md").write_text("# Stepper X")

        def build_tree(path: Path, prefix: str = "") -> list[str]:
            lines = []
            entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))

            for i, entry in enumerate(entries):
                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "

                if entry.is_dir():
                    lines.append(f"{prefix}{connector}{entry.name}/")
                    extension = "    " if is_last else "│   "
                    lines.extend(build_tree(entry, prefix + extension))
                else:
                    lines.append(f"{prefix}{connector}{entry.name}")

            return lines

        lines = ["docs/"] + build_tree(docs_path)

        print("=== Test 4: Tree structure ===")
        for line in lines:
            print(f"  {line}")

        assert "README.md" in "\n".join(lines), "Should show README.md"
        assert "config/" in "\n".join(lines), "Should show config/ folder"
        assert "stepper_x.md" in "\n".join(lines), "Should show nested file"
        print("  ✓ PASSED\n")


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("MANUAL SERVER LOGIC TESTS")
    print("=" * 50 + "\n")

    test_search_logic()
    test_read_doc_logic()
    test_tree_structure()

    print("=" * 50)
    print("ALL TESTS PASSED ✓")
    print("=" * 50)
