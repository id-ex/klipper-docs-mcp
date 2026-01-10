"""Custom exceptions for Klipper Docs MCP Server."""


class KlipperDocsError(Exception):
    """Base exception for Klipper Docs MCP Server errors."""

    pass


class ResourceNotFoundError(KlipperDocsError):
    """Raised when a requested documentation resource is not found."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Documentation file not found: {path}")


class PathTraversalError(KlipperDocsError):
    """Raised when a path traversal attempt is detected."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Access denied: path traversal attempt: {path}")


class InvalidPathError(KlipperDocsError):
    """Raised when an invalid path is provided."""

    def __init__(self, path: str, reason: str = "invalid path"):
        self.path = path
        super().__init__(f"Access denied: {reason}: {path}")


class DocumentationNotAvailableError(KlipperDocsError):
    """Raised when documentation directory is not available."""

    def __init__(self, message: str = "Documentation directory not found. Run sync_docs() first."):
        super().__init__(message)


class GitOperationError(KlipperDocsError):
    """Raised when a Git operation fails."""

    def __init__(self, repo_name: str, operation: str, details: str = ""):
        self.repo_name = repo_name
        self.operation = operation
        self.details = details
        message = f"Git operation '{operation}' failed for {repo_name}"
        if details:
            message += f": {details}"
        super().__init__(message)


class SearchQueryEmptyError(KlipperDocsError):
    """Raised when an empty search query is provided."""

    def __init__(self, message: str = "Please provide a search query."):
        super().__init__(message)
