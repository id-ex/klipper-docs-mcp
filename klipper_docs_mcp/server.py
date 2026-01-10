"""MCP Server for Klipper Documentation.

Local documentation access optimized for low-resource devices (Raspberry Pi).
"""

import asyncio
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool

from .config import (
    DOCS_DIR,
    MAX_FILE_CHARS,
    MAX_SEARCH_RESULTS,
    SYNC_DESCRIPTION,
)
from .exceptions import KlipperDocsError
from .services import GitManager, SearchEngine, StorageManager

try:
    from . import __version__
except ImportError:
    __version__ = "0.0.0-dev"

# Initialize services
_storage_manager = StorageManager()
_git_manager = GitManager()
_search_engine = SearchEngine(docs_dir=DOCS_DIR)

app = Server("klipper-docs-server")
_docs_outdated = False


@app.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """List available documentation resources."""
    resources = []

    if not _storage_manager.is_available():
        return resources

    for rel_path in _storage_manager.list_files():
        path_str = str(rel_path)
        resources.append(
            types.Resource(
                uri=f"file://{path_str}",
                name=path_str,
                description=f"Klipper documentation: {rel_path}",
                mimeType="text/markdown",
            )
        )

    return resources


@app.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read a documentation resource by URI."""
    # Remove file:// prefix if present
    if uri.startswith("file://"):
        path = uri[7:]
    else:
        path = uri
    content, _ = _storage_manager.read_file(path)
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
    """Search documentation by query."""
    try:
        results = _search_engine.search(query)
        formatted = _search_engine.format_results(results)
        return [types.TextContent(type="text", text=formatted)]
    except KlipperDocsError as e:
        return [types.TextContent(type="text", text=str(e))]


async def read_doc(path: str, offset: int = 0, limit: int = MAX_FILE_CHARS) -> list[types.TextContent]:
    """Read a documentation file by relative path with optional pagination."""
    try:
        content, total_chars = _storage_manager.read_file(path, offset, limit)
        end = offset + limit

        output = content
        if offset > 0 or end < total_chars:
            output += f"\n\n[... Showing characters {offset}-{min(end, total_chars)} of {total_chars} total]"

        return [types.TextContent(type="text", text=output)]
    except KlipperDocsError as e:
        return [types.TextContent(type="text", text=str(e))]


async def list_docs_map() -> list[types.TextContent]:
    """List the documentation structure as a tree."""
    if not _storage_manager.is_available():
        return [types.TextContent(type="text", text="Documentation directory not found. Run sync_docs() first.")]

    root_name = _storage_manager.docs_dir.name
    lines = [f"{root_name}/"] + _storage_manager.build_tree()

    return [types.TextContent(type="text", text="\n".join(lines))]


async def sync_docs() -> list[types.TextContent]:
    """Sync documentation with remote repositories."""
    global _docs_outdated

    output_lines = []
    results = _git_manager.sync_all()

    for result in results:
        output_lines.append(f"\n--- Syncing {result.repo_name} ---")
        if result.success:
            if result.was_cloned:
                output_lines.append(f"Cloning {result.repo_name}...")
            elif result.was_updated:
                output_lines.append(f"Updating {result.repo_name}...")
            output_lines.append(result.message)
        else:
            output_lines.append(result.message)

    # Check status after sync
    _docs_outdated = _git_manager.check_if_outdated()
    if not _docs_outdated:
        output_lines.append("\nAll documentation repositories are up to date.")

    return [types.TextContent(type="text", text="\n".join(output_lines))]


async def main():
    """Main entry point for the MCP server."""
    global _docs_outdated

    # Check for updates on startup (non-blocking)
    _docs_outdated = _git_manager.check_if_outdated()

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
