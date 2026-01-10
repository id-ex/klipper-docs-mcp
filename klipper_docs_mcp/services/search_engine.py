"""Search Engine for Klipper Docs MCP Server.

Handles searching through documentation files with ranking and context extraction.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..config import SearchConfig, StorageConfig
from ..exceptions import DocumentationNotAvailableError, SearchQueryEmptyError


@dataclass
class SearchResult:
    """A single search result."""

    rank: int
    path: str
    snippet: str


class SearchEngine:
    """Searches through documentation files."""

    def __init__(
        self,
        docs_dir: Path,
        search_config: Optional[SearchConfig] = None,
        storage_config: Optional[StorageConfig] = None,
    ):
        """Initialize the search engine.

        Args:
            docs_dir: Path to the documentation directory.
            search_config: Search configuration. If None, uses default.
            storage_config: Storage configuration for file extensions. If None, uses default.
        """
        self.docs_dir = docs_dir
        self.search_config = search_config or SearchConfig()
        self.storage_config = storage_config or StorageConfig()

    def _is_supported_file(self, filename: str) -> bool:
        """Check if file is supported for searching.

        Args:
            filename: Name of the file.

        Returns:
            True if file has supported extension.
        """
        return filename.endswith(self.storage_config.supported_extensions)

    def _extract_heading_matches(self, content: str, query: str) -> list[tuple[int, str]]:
        """Extract matches from Markdown headings.

        Args:
            content: File content to search.
            query: Search query.

        Returns:
            List of (position, snippet) tuples for heading matches.
        """
        matches = []
        heading_pattern = re.compile(
            r"^(#{1,6}\s.*" + re.escape(query) + ".*)$",
            re.MULTILINE | re.IGNORECASE,
        )

        heading_ranges = []
        for match in heading_pattern.finditer(content):
            start = max(0, match.start() - 50)
            end = min(len(content), match.end() + 50)
            snippet = content[start:end].strip()
            matches.append((match.start(), "heading", snippet))
            heading_ranges.append((match.start(), match.end()))

        return matches, heading_ranges

    def _extract_content_matches(
        self, content: str, query: str, heading_ranges: list[tuple[int, int]]
    ) -> list[tuple[int, str, str]]:
        """Extract matches from regular content (non-heading).

        Args:
            content: File content to search.
            query: Search query.
            heading_ranges: Ranges of heading matches to exclude.

        Returns:
            List of (position, type, snippet) tuples for content matches.
        """
        matches = []

        for match in re.finditer(re.escape(query), content, re.IGNORECASE):
            # Check if match overlaps with any heading
            is_heading = False
            for h_start, h_end in heading_ranges:
                if match.start() >= h_start and match.end() <= h_end:
                    is_heading = True
                    break

            if is_heading:
                continue

            snippet_length = self.search_config.snippet_length
            start = max(0, match.start() - snippet_length // 2)
            end = min(len(content), match.end() + snippet_length // 2)
            snippet = content[start:end].strip()
            matches.append((match.start(), "content", snippet))

        return matches

    def _determine_rank(self, filename_match: bool, matches: list) -> int:
        """Determine search result rank based on match type.

        Args:
            filename_match: Whether query matched in filename.
            matches: List of content matches.

        Returns:
            Rank value (1=highest, 3=lowest).
        """
        if filename_match:
            return 1
        elif any(m[1] == "heading" for m in matches):
            return 2
        else:
            return 3

    def _get_best_snippet(self, content: str, matches: list) -> str:
        """Get the best snippet for search results.

        Args:
            content: File content.
            matches: List of matches.

        Returns:
            Best snippet string.
        """
        if matches:
            matches.sort(key=lambda x: x[0])
            return matches[0][2]
        else:
            # Filename match - show file start
            snippet_length = self.search_config.snippet_length
            if len(content) > snippet_length:
                return content[:snippet_length] + "..."
            return content

    def search(self, query: str) -> list[SearchResult]:
        """Search documentation by query.

        Prioritizes matches in:
        1. Filenames
        2. Markdown headings (lines starting with #)
        3. Regular content

        Args:
            query: Search query string.

        Returns:
            List of SearchResult objects, ranked by relevance.

        Raises:
            DocumentationNotAvailableError: If docs directory doesn't exist.
            SearchQueryEmptyError: If query is empty.
        """
        if not self.docs_dir.exists():
            raise DocumentationNotAvailableError()

        if not query:
            raise SearchQueryEmptyError()

        query_lower = query.lower()
        results = []

        # Stream through files to avoid loading everything into memory
        for root, dirs, files in os.walk(self.docs_dir):
            for file in files:
                if not self._is_supported_file(file):
                    continue

                file_path = Path(root) / file
                rel_path = str(file_path.relative_to(self.docs_dir))

                try:
                    # Check filename match (highest priority)
                    filename_match = query_lower in rel_path.lower()

                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    # Extract heading matches
                    heading_matches, heading_ranges = self._extract_heading_matches(content, query)

                    # Extract content matches
                    content_matches = self._extract_content_matches(content, query, heading_ranges)

                    # Combine all matches
                    all_matches = heading_matches + content_matches

                    # Add result if we have matches or filename match
                    if all_matches or filename_match:
                        rank = self._determine_rank(filename_match, all_matches)
                        snippet = self._get_best_snippet(content, all_matches)
                        results.append(SearchResult(rank=rank, path=rel_path, snippet=snippet))

                except (IOError, UnicodeDecodeError):
                    continue

        # Sort by rank and limit results
        results.sort(key=lambda x: x.rank)
        max_results = self.search_config.max_results
        return results[:max_results]

    def format_results(self, results: list[SearchResult]) -> str:
        """Format search results for display.

        Args:
            results: List of SearchResult objects.

        Returns:
            Formatted string output.
        """
        if not results:
            return "No results found."

        output = []
        for result in results:
            output.append(f"## {result.path}\n{result.snippet}\n")

        return "\n".join(output)
