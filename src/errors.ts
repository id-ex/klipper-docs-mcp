import { McpError, ErrorCode } from "@modelcontextprotocol/sdk/types.js";

/** Base exception for Klipper Docs MCP Server errors. */
export class KlipperDocsError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "KlipperDocsError";
  }
}

/** Raised when a requested documentation resource is not found. */
export class ResourceNotFoundError extends KlipperDocsError {
  constructor(path: string) {
    super(`Documentation file not found: ${path}`);
    this.name = "ResourceNotFoundError";
  }
}

/** Raised when a path traversal attempt is detected. */
export class PathTraversalError extends KlipperDocsError {
  constructor(path: string) {
    super(`Access denied: path traversal attempt: ${path}`);
    this.name = "PathTraversalError";
  }
}

/** Raised when an invalid path is provided. */
export class InvalidPathError extends KlipperDocsError {
  constructor(path: string, reason: string = "invalid path") {
    super(`Access denied: ${reason}: ${path}`);
    this.name = "InvalidPathError";
  }
}

/** Raised when documentation directory is not available. */
export class DocumentationNotAvailableError extends KlipperDocsError {
  constructor(message: string = "Documentation directory not found. Run sync_docs() first.") {
    super(message);
    this.name = "DocumentationNotAvailableError";
  }
}

/** Raised when a Git operation fails. */
export class GitOperationError extends KlipperDocsError {
  constructor(repoName: string, operation: string, details: string = "") {
    let message = `Git operation '${operation}' failed for ${repoName}`;
    if (details) {
      message += `: ${details}`;
    }
    super(message);
    this.name = "GitOperationError";
  }
}

/** Raised when an empty search query is provided. */
export class SearchQueryEmptyError extends KlipperDocsError {
  constructor(message: string = "Please provide a search query.") {
    super(message);
    this.name = "SearchQueryEmptyError";
  }
}
