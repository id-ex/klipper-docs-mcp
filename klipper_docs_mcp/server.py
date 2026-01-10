"""MCP Server for Klipper Documentation.

Local documentation access optimized for low-resource devices (Raspberry Pi).
"""

import asyncio
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool

try:
    from . import __version__
except ImportError:
    __version__ = "0.0.0-dev"

# Constants
KLIPPER_REPO_URL = "https://github.com/Klipper3d/klipper.git"
DOCS_DIR = Path(os.getenv("KLIPPER_DOCS_PATH", "./docs")).resolve()
MAX_FILE_CHARS = 10000
SNIPPET_LENGTH = 200
MAX_SEARCH_RESULTS = 7
SYNC_DESCRIPTION = "Sync documentation with remote repository (git pull --depth 1)"

app = Server("klipper-docs-server")
_docs_outdated = False


@app.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """List available documentation resources."""
    resources = []

    if not DOCS_DIR.exists():
        return resources

    for root, dirs, files in os.walk(DOCS_DIR):
        for file in files:
            if file.endswith((".md", ".txt")):
                full_path = Path(root) / file
                rel_path = full_path.relative_to(DOCS_DIR)
                resources.append(
                    types.Resource(
                        uri=str(rel_path),
                        name=str(rel_path),
                        description=f"Klipper documentation: {rel_path}",
                        mimeType="text/markdown",
                    )
                )

    return resources


@app.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read a documentation resource by URI."""
    file_path = (DOCS_DIR / uri).resolve()

    # Security check: ensure path is within DOCS_DIR
    if not str(file_path).startswith(str(DOCS_DIR)):
        raise ValueError(f"Access denied: path traversal attempt: {uri}")

    if not file_path.exists():
        raise FileNotFoundError(f"Documentation file not found: {uri}")

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    if len(content) > MAX_FILE_CHARS:
        content = content[:MAX_FILE_CHARS] + f"\n\n[... File truncated ({len(content)} total chars)]"

    return content


@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available MCP tools."""
    description = SYNC_DESCRIPTION
    if _docs_outdated:
        description += " (РЕКОМЕНДУЕТСЯ: база устарела)"

    return [
        Tool(
            name="search_docs",
            description="Search Klipper documentation by query. Returns up to 7 results with file paths and snippets. Matches in filenames and headings are ranked higher.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query - searches through filenames and document content",
                    }
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="read_doc",
            description=f"Read a Klipper documentation file. Returns up to {MAX_FILE_CHARS} characters by default. Use offset and limit for pagination.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the documentation file (e.g., 'Config_Reference.md' or 'prints/bed_mesh.md')",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Character offset to start reading from (default: 0)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": f"Number of characters to read (default: {MAX_FILE_CHARS})",
                    },
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="list_docs_map",
            description="List the complete structure of Klipper documentation as a tree. Useful for discovering available files and understanding the docs organization.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="sync_docs",
            description=description,
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handle tool calls."""
    if name == "search_docs":
        return await search_docs(arguments.get("query", ""))
    elif name == "read_doc":
        offset = arguments.get("offset", 0)
        limit = arguments.get("limit", MAX_FILE_CHARS)
        return await read_doc(arguments.get("path", ""), offset, limit)
    elif name == "list_docs_map":
        return await list_docs_map()
    elif name == "sync_docs":
        return await sync_docs()
    else:
        raise ValueError(f"Unknown tool: {name}")


async def search_docs(query: str) -> list[types.TextContent]:
    """Search documentation by query.

    Prioritizes matches in:
    1. Filenames
    2. Markdown headings (lines starting with #)
    3. Regular content
    """
    if not DOCS_DIR.exists():
        return [types.TextContent(type="text", text="Documentation directory not found. Run sync_docs() first.")]

    if not query:
        return [types.TextContent(type="text", text="Please provide a search query.")]

    results = []
    query_lower = query.lower()

    # Stream through files to avoid loading everything into memory
    for root, dirs, files in os.walk(DOCS_DIR):
        for file in files:
            if file.endswith((".md", ".txt")):
                file_path = Path(root) / file
                rel_path = file_path.relative_to(DOCS_DIR)

                try:
                    # Check filename match (highest priority)
                    filename_match = query_lower in str(rel_path).lower()

                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    # Search for matches with context
                    matches = []

                    # Search in headings (#, ##, etc.)
                    heading_pattern = re.compile(r"^(#{1,6}\s.*" + re.escape(query) + ".*)$", re.MULTILINE | re.IGNORECASE)
                    for match in heading_pattern.finditer(content):
                        start = max(0, match.start() - 50)
                        end = min(len(content), match.end() + 50)
                        snippet = content[start:end].strip()
                        matches.append((match.start(), "heading", snippet))

                    # Search in content
                    for match in re.finditer(re.escape(query), content, re.IGNORECASE):
                        start = max(0, match.start() - SNIPPET_LENGTH // 2)
                        end = min(len(content), match.end() + SNIPPET_LENGTH // 2)
                        snippet = content[start:end].strip()
                        matches.append((match.start(), "content", snippet))

                    if matches or filename_match:
                        # Determine rank
                        rank = 3
                        if filename_match:
                            rank = 1
                        elif any(m[1] == "heading" for m in matches):
                            rank = 2

                        # Get best snippet
                        best_snippet = ""
                        if matches:
                            matches.sort(key=lambda x: x[0])
                            best_snippet = matches[0][2]
                        else:
                            # Filename match - show file start
                            best_snippet = content[:SNIPPET_LENGTH] + "..." if len(content) > SNIPPET_LENGTH else content

                        results.append((rank, str(rel_path), best_snippet))

                except (IOError, UnicodeDecodeError):
                    continue

    # Sort by rank and limit results
    results.sort(key=lambda x: x[0])
    results = results[:MAX_SEARCH_RESULTS]

    if not results:
        return [types.TextContent(type="text", text=f"No results found for '{query}'")]

    output = []
    for rank, path, snippet in results:
        output.append(f"## {path}\n{snippet}\n")

    return [types.TextContent(type="text", text="\n".join(output))]


async def read_doc(path: str, offset: int = 0, limit: int = MAX_FILE_CHARS) -> list[types.TextContent]:
    """Read a documentation file by relative path with optional pagination."""
    if not DOCS_DIR.exists():
        return [types.TextContent(type="text", text="Documentation directory not found. Run sync_docs() first.")]

    # Security check: normalize and validate path
    target_path = (DOCS_DIR / path).resolve()

    try:
        common_path = os.path.commonpath([DOCS_DIR, target_path])
        if common_path != str(DOCS_DIR):
            return [types.TextContent(type="text", text="Access denied: path traversal attempt")]
    except ValueError:
        return [types.TextContent(type="text", text="Access denied: invalid path")]

    if not target_path.exists():
        return [types.TextContent(type="text", text=f"File not found: {path}\n\nUse list_docs_map() to see available files.")]

    try:
        with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        total_chars = len(content)
        end = offset + limit
        content_slice = content[offset:end]
        
        truncated = False
        if end < total_chars:
            truncated = True

        output = content_slice
        
        if offset > 0 or truncated:
            output += f"\n\n[... Showing characters {offset}-{min(end, total_chars)} of {total_chars} total]"

        return [types.TextContent(type="text", text=output)]
    except IOError as e:
        return [types.TextContent(type="text", text=f"Error reading file: {e}")]


async def list_docs_map() -> list[types.TextContent]:
    """List the documentation structure as a tree."""
    if not DOCS_DIR.exists():
        return [types.TextContent(type="text", text="Documentation directory not found. Run sync_docs() first.")]

    def build_tree(path: Path, prefix: str = "", is_last: bool = True) -> list[str]:
        """Recursively build directory tree representation."""
        lines = []
        try:
            entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            entries = [e for e in entries if not e.name.startswith(".")]
        except PermissionError:
            return lines

        for i, entry in enumerate(entries):
            is_last_entry = i == len(entries) - 1
            connector = "└── " if is_last_entry else "├── "

            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                extension = "    " if is_last_entry else "│   "
                lines.extend(build_tree(entry, prefix + extension, is_last_entry))
            else:
                lines.append(f"{prefix}{connector}{entry.name}")

        return lines

    root_name = DOCS_DIR.name
    lines = [f"{root_name}/"] + build_tree(DOCS_DIR)

    return [types.TextContent(type="text", text="\n".join(lines))]


async def sync_docs() -> list[types.TextContent]:
    """Sync documentation with remote repository."""
    global _docs_outdated

    output_lines = []
    error_lines = []

    try:
        # Check if docs directory exists and is a git repo
        if not DOCS_DIR.exists():
            output_lines.append(f"Documentation directory not found at: {DOCS_DIR}")
            output_lines.append("Initializing sparse checkout...")

            # Create parent directory if needed
            DOCS_DIR.parent.mkdir(parents=True, exist_ok=True)

            # Initialize sparse checkout
            result = subprocess.run(
                [
                    "git", "clone", "--depth=1", "--no-checkout",
                    KLIPPER_REPO_URL, str(DOCS_DIR)
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                return [types.TextContent(type="text", text=f"Clone failed:\n{result.stderr}")]

            # Configure sparse checkout
            subprocess.run(["git", "config", "core.sparseCheckout", "true"],
                          cwd=DOCS_DIR, capture_output=True)
            subprocess.run(["git", "sparse-checkout", "set", "docs/"],
                          cwd=DOCS_DIR, capture_output=True)
            subprocess.run(["git", "checkout"], cwd=DOCS_DIR, capture_output=True)

            # Move docs/* to parent directory
            docs_subdir = DOCS_DIR / "docs"
            if docs_subdir.exists():
                for item in docs_subdir.iterdir():
                    dest = DOCS_DIR / item.name
                    if dest.exists():
                        subprocess.run(["rm", "-rf", str(dest)], capture_output=True)
                    subprocess.run(["mv", str(item), str(DOCS_DIR)], capture_output=True)
                subprocess.run(["rm", "-rf", str(docs_subdir)], capture_output=True)

            output_lines.append("Documentation initialized successfully.")
        else:
            # Existing repo - do a pull
            output_lines.append("Syncing with remote repository...")

            result = subprocess.run(
                ["git", "pull", "--depth=1"],
                cwd=DOCS_DIR,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                return [types.TextContent(type="text", text=f"Pull failed:\n{result.stderr}")]

            output_lines.append(result.stdout or "Already up to date.")

        # Check status after sync
        _docs_outdated = await check_if_outdated()
        if not _docs_outdated:
            output_lines.append("\nDocumentation is up to date.")

        return [types.TextContent(type="text", text="\n".join(output_lines))]

    except subprocess.TimeoutExpired:
        return [types.TextContent(type="text", text="Operation timed out (5 minutes).")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Sync error: {e}")]


async def check_if_outdated() -> bool:
    """Check if local documentation is outdated compared to remote.

    Returns True if updates are available.
    """
    global _docs_outdated

    if not DOCS_DIR.exists():
        return False

    try:
        # Fetch without downloading data
        subprocess.run(
            ["git", "fetch"],
            cwd=DOCS_DIR,
            capture_output=True,
            timeout=60,
        )

        # Compare HEAD with remote
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
            local_hash = local_rev.stdout.strip()
            remote_hash = remote_rev.stdout.strip()
            is_outdated = local_hash != remote_hash

            if is_outdated:
                import sys
                print(f"\n[INFO] Documentation update available. Run sync_docs() to update.", file=sys.stderr)

            return is_outdated

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return False


async def main():
    """Main entry point for the MCP server."""
    global _docs_outdated

    # Check for updates on startup (non-blocking)
    _docs_outdated = await check_if_outdated()

    # Run the server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="klipper-docs-server",
                server_version=__version__,
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
