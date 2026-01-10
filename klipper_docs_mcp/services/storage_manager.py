"""Storage Manager for Klipper Docs MCP Server.

Handles file system operations including reading files and listing documentation structure.
"""

import os
from pathlib import Path
from typing import Optional

from ..config import StorageConfig
from ..exceptions import (
    DocumentationNotAvailableError,
    InvalidPathError,
    PathTraversalError,
    ResourceNotFoundError,
)


class StorageManager:
    """Manages file system operations for documentation access."""

    def __init__(self, config: Optional[StorageConfig] = None):
        """Initialize the storage manager.

        Args:
            config: Storage configuration. If None, uses default config.
        """
        self.config = config or StorageConfig()

    @property
    def docs_dir(self) -> Path:
        """Get the documentation directory path."""
        return self.config.docs_dir

    def is_available(self) -> bool:
        """Check if documentation directory exists and is accessible."""
        return self.docs_dir.exists()

    def require_available(self) -> None:
        """Raise an exception if documentation is not available."""
        if not self.is_available():
            raise DocumentationNotAvailableError()

    def validate_path(self, path: str) -> Path:
        """Validate and resolve a path, ensuring it's within docs directory.

        Args:
            path: Relative path to validate.

        Returns:
            Resolved absolute path.

        Raises:
            InvalidPathError: If path is invalid or outside docs directory.
            PathTraversalError: If path traversal attempt is detected.
        """
        target_path = (self.docs_dir / path).resolve()

        try:
            common_path = os.path.commonpath([self.docs_dir, target_path])
            if common_path != str(self.docs_dir):
                raise PathTraversalError(path)
        except ValueError:
            raise InvalidPathError(path, reason="invalid path")

        return target_path

    def read_file(self, path: str, offset: int = 0, limit: Optional[int] = None) -> tuple[str, int]:
        """Read a documentation file.

        Args:
            path: Relative path to the file.
            offset: Character offset to start reading from.
            limit: Maximum number of characters to read.

        Returns:
            Tuple of (content, total_chars).

        Raises:
            DocumentationNotAvailableError: If docs directory doesn't exist.
            ResourceNotFoundError: If the specified file doesn't exist.
            InvalidPathError: If path is invalid.
        """
        self.require_available()
        limit = limit or self.config.max_file_chars

        target_path = self.validate_path(path)

        if not target_path.exists():
            raise ResourceNotFoundError(path)

        with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        total_chars = len(content)
        end = offset + limit
        content_slice = content[offset:end]

        return content_slice, total_chars

    def list_files(self) -> list[Path]:
        """List all documentation files.

        Returns:
            List of relative paths to documentation files.

        Raises:
            DocumentationNotAvailableError: If docs directory doesn't exist.
        """
        self.require_available()

        files = []
        for root, dirs, filenames in os.walk(self.docs_dir):
            for filename in filenames:
                if filename.endswith(self.config.supported_extensions):
                    full_path = Path(root) / filename
                    rel_path = full_path.relative_to(self.docs_dir)
                    files.append(rel_path)

        return files

    def build_tree(self, path: Optional[Path] = None, prefix: str = "", is_last: bool = True) -> list[str]:
        """Recursively build directory tree representation.

        Args:
            path: Path to build tree from. Defaults to docs_dir.
            prefix: Prefix for each line (used for recursion).
            is_last: Whether current entry is the last in its parent.

        Returns:
            List of strings representing the tree structure.
        """
        if path is None:
            path = self.docs_dir

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
                lines.extend(self.build_tree(entry, prefix + extension, is_last_entry))
            else:
                lines.append(f"{prefix}{connector}{entry.name}")

        return lines
