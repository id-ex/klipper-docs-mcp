"Manual tests for server logic without MCP SDK."

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
        
        # Create klipper repo
        klipper_path = docs_path / "klipper"
        klipper_path.mkdir()

        # Create test files
        (klipper_path / "README.md").write_text("# Klipper\n\nWelcome to Klipper 3D printer firmware.")
        (klipper_path / "Config_Reference.md").write_text(
            "# Config Reference\n\n" +
            "stepper_x:\n" +
            "  step_pin: P1.20"
        )
        (klipper_path / "prints").mkdir()
        (klipper_path / "prints" / "bed_mesh.md").write_text(
            "# Bed Mesh\n\n" +
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
        klipper_path = docs_path / "klipper"
        klipper_path.mkdir()

        (klipper_path / "test.md").write_text("x" * 15000)  # Large file
        (klipper_path / "safe.md").write_text("Safe content")

        # Test 1: Truncation
        with open(klipper_path / "test.md") as f:
            content = f.read()

        MAX_FILE_CHARS = 10000
        if len(content) > MAX_FILE_CHARS:
            content = content[:MAX_FILE_CHARS] + f"\n\n[... Showing characters 0-{MAX_FILE_CHARS} of {len(content)} total]"

        print("=== Test 2: File truncation ===")
        print(f"  Original: 15000 chars")
        print(f"  After: {len(content)} chars")
        assert len(content) <= MAX_FILE_CHARS + 200, "Should be truncated"
        assert "Showing characters" in content, "Should have truncation marker"
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
        
        # Structure: docs/klipper/config/printer.md
        klipper_path = docs_path / "klipper"
        klipper_path.mkdir()
        (klipper_path / "README.md").write_text("# Readme")
        
        config_path = klipper_path / "config"
        config_path.mkdir()
        (config_path / "printer.md").write_text("# Printer Config")
        
        steppers_path = config_path / "steppers"
        steppers_path.mkdir()
        (steppers_path / "stepper_x.md").write_text("# Stepper X")

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

        assert "klipper/" in "\n".join(lines), "Should show repo folder"
        assert "printer.md" in "\n".join(lines), "Should show file"
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