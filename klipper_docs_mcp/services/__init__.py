"""Services module for Klipper Docs MCP Server.

This module contains the core business logic for the documentation server,
separated from the MCP protocol layer.
"""

from .git_manager import GitManager, SyncResult
from .search_engine import SearchEngine, SearchResult
from .storage_manager import StorageManager

__all__ = [
    "GitManager",
    "SyncResult",
    "SearchEngine",
    "SearchResult",
    "StorageManager",
]
