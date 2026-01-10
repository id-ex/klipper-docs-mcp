"""Standalone test server - simulates MCP without the SDK dependency.

This version allows testing the server logic locally without installing mcp.
"""

import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


# Constants
KLIPPER_REPO_URL = "https://github.com/Klipper3d/klipper.git"
DOCS_DIR = Path(os.getenv("KLIPPER_DOCS_PATH", "./docs")).resolve()
MAX_FILE_CHARS = 10000
SNIPPET_LENGTH = 200
MAX_SEARCH_RESULTS = 7


class StandaloneServer:
    """Standalone server for testing without MCP SDK."""

    def __init__(self):
        self._docs_outdated = False

    async def check_if_outdated(self) -> bool:
        """Check if local documentation is outdated."""
        if not DOCS_DIR.exists():
            return False

        try:
            subprocess.run(
                ["git", "fetch"],
                cwd=DOCS_DIR,
                capture_output=True,
                timeout=60,
            )

            local_rev = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=DOCS_DIR,
                capture_output=True,
                text=True,
                timeout=10,
            )
            remote_rev = subprocess.run(
                ["git", "rev-parse", "@{u}"],
                cwd=DOCS_DIR,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if local_rev.returncode == 0 and remote_rev.returncode == 0:
                return local_rev.stdout.strip() != remote_rev.stdout.strip()

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return False

    async def search_docs(self, query: str) -> str:
        """Search documentation by query."""
        if not DOCS_DIR.exists():
            return "Documentation directory not found. Run sync_docs() first."

        if not query:
            return "Please provide a search query."

        results = []
        query_lower = query.lower()

        for root, dirs, files in os.walk(DOCS_DIR):
            for file in files:
                if file.endswith((".md", ".txt")):
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(DOCS_DIR)

                    try:
                        filename_match = query_lower in str(rel_path).lower()

                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                        matches = []
                        heading_pattern = re.compile(r"^(#{1,6}\s.*" + re.escape(query) + ".*)$", re.MULTILINE | re.IGNORECASE)
                        for match in heading_pattern.finditer(content):
                            start = max(0, match.start() - 50)
                            end = min(len(content), match.end() + 50)
                            snippet = content[start:end].strip()
                            matches.append((match.start(), "heading", snippet))

                        for match in re.finditer(re.escape(query), content, re.IGNORECASE):
                            start = max(0, match.start() - SNIPPET_LENGTH // 2)
                            end = min(len(content), match.end() + SNIPPET_LENGTH // 2)
                            snippet = content[start:end].strip()
                            matches.append((match.start(), "content", snippet))

                        if matches or filename_match:
                            rank = 3
                            if filename_match:
                                rank = 1
                            elif any(m[1] == "heading" for m in matches):
                                rank = 2

                            best_snippet = ""
                            if matches:
                                matches.sort(key=lambda x: x[0])
                                best_snippet = matches[0][2]
                            else:
                                best_snippet = content[:SNIPPET_LENGTH] + "..." if len(content) > SNIPPET_LENGTH else content

                            results.append((rank, str(rel_path), best_snippet))

                    except (IOError, UnicodeDecodeError):
                        continue

        results.sort(key=lambda x: x[0])
        results = results[:MAX_SEARCH_RESULTS]

        if not results:
            return f"No results found for '{query}'"

        output = []
        for rank, path, snippet in results:
            output.append(f"## {path}\n{snippet}\n")

        return "\n".join(output)

    async def read_doc(self, path: str) -> str:
        """Read a documentation file."""
        if not DOCS_DIR.exists():
            return "Documentation directory not found. Run sync_docs() first."

        target_path = (DOCS_DIR / path).resolve()

        try:
            common_path = os.path.commonpath([DOCS_DIR, target_path])
            if common_path != str(DOCS_DIR):
                return f"Access denied: path traversal attempt"
        except ValueError:
            return f"Access denied: invalid path"

        if not target_path.exists():
            return f"File not found: {path}\n\nUse list_docs_map() to see available files."

        try:
            with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if len(content) > MAX_FILE_CHARS:
                content = content[:MAX_FILE_CHARS]
                total_chars = len(content)
                content += f"\n\n[... File truncated: {total_chars} of {MAX_FILE_CHARS} characters shown]"

            return content
        except IOError as e:
            return f"Error reading file: {e}"

    async def list_docs_map(self) -> str:
        """List documentation structure."""
        if not DOCS_DIR.exists():
            return "Documentation directory not found. Run sync_docs() first."

        def build_tree(path: Path, prefix: str = "") -> list[str]:
            lines = []
            try:
                entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                entries = [e for e in entries if not e.name.startswith(".")]
            except PermissionError:
                return lines

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

        lines = [f"{DOCS_DIR.name}/"] + build_tree(DOCS_DIR)
        return "\n".join(lines)


async def interactive_shell():
    """Interactive shell for testing."""
    server = StandaloneServer()

    print("=" * 50)
    print("KLIPPER DOCS STANDALONE SERVER")
    print("=" * 50)
    print(f"\nDocs directory: {DOCS_DIR}")
    print(f"Docs exist: {DOCS_DIR.exists()}")
    print("\nCommands:")
    print("  search <query>     - Search documentation")
    print("  read <path>        - Read a file")
    print("  list               - List docs structure")
    print("  check              - Check for updates")
    print("  quit               - Exit")
    print("=" * 50)

    # Check for updates on startup
    server._docs_outdated = await server.check_if_outdated()
    if server._docs_outdated:
        print("\n[INFO] Documentation update available!")

    while True:
        try:
            cmd = input("\n> ").strip()
            if not cmd:
                continue

            parts = cmd.split(maxsplit=1)
            action = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if action == "quit" or action == "exit":
                break

            elif action == "search":
                if not arg:
                    print("Usage: search <query>")
                else:
                    result = await server.search_docs(arg)
                    print(result)

            elif action == "read":
                if not arg:
                    print("Usage: read <path>")
                else:
                    result = await server.read_doc(arg)
                    print(result)

            elif action == "list":
                result = await server.list_docs_map()
                print(result)

            elif action == "check":
                is_outdated = await server.check_if_outdated()
                print(f"Documentation is {'OUTDATED' if is_outdated else 'up to date'}")

            else:
                print(f"Unknown command: {action}")

        except KeyboardInterrupt:
            print("\nUse 'quit' to exit.")
        except EOFError:
            break


async def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        await interactive_shell()
    else:
        # Demo mode - run a few tests
        server = StandaloneServer()

        print("\n=== KLIPPER DOCS STANDALONE SERVER ===\n")
        print(f"Docs directory: {DOCS_DIR}")
        print(f"Docs exist: {DOCS_DIR.exists()}")

        if DOCS_DIR.exists():
            print("\n--- File listing ---")
            result = await server.list_docs_map()
            print(result[:500] + "..." if len(result) > 500 else result)
        else:
            print("\nDocs not found. Run sync_docs() first.")


if __name__ == "__main__":
    asyncio.run(main())
