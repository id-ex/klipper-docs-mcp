"""Configuration module for Klipper Docs MCP Server.

Contains constants and configuration settings.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


# Repository configurations
REPOSITORIES = {
    "klipper": {
        "url": "https://github.com/Klipper3d/klipper.git",
        "sparse_path": "docs/",
    },
    "moonraker": {
        "url": "https://github.com/Arksine/moonraker.git",
        "sparse_path": "docs/",
    },
}

# Documentation directory
DOCS_DIR = Path(os.getenv("KLIPPER_DOCS_PATH", "./docs")).resolve()

# File reading limits
MAX_FILE_CHARS = 10000
SNIPPET_LENGTH = 200
MAX_SEARCH_RESULTS = 7

# Tool descriptions
SYNC_DESCRIPTION = "Sync documentation (Klipper, Moonraker) with remote repositories"


@dataclass
class SearchConfig:
    """Configuration for search operations."""

    snippet_length: int = SNIPPET_LENGTH
    max_results: int = MAX_SEARCH_RESULTS


@dataclass
class StorageConfig:
    """Configuration for storage operations."""

    docs_dir: Path = field(default_factory=lambda: DOCS_DIR)
    max_file_chars: int = MAX_FILE_CHARS
    supported_extensions: tuple = (".md", ".txt")


@dataclass
class GitConfig:
    """Configuration for Git operations."""

    repositories: dict = field(default_factory=lambda: REPOSITORIES)
    docs_dir: Path = field(default_factory=lambda: DOCS_DIR)
    clone_timeout: int = 300
    fetch_timeout: int = 60
    rev_parse_timeout: int = 10
