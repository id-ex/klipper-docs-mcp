# Klipper Docs MCP Server

## Project Overview
This project serves as a Model Context Protocol (MCP) server that provides local access to Klipper 3D printer documentation. It is specifically designed for low-resource environments, such as Raspberry Pi, by avoiding heavy database dependencies and utilizing efficient file-based operations.

**Key Features:**
*   **Local Search:** Performs searches directly on the file system without external APIs.
*   **Resource Efficiency:** Uses streaming and generator patterns to minimize RAM/CPU usage.
*   **Synchronization:** Includes tools to sync with the official Klipper GitHub repository via `git`.
*   **Security:** Implements path traversal protection for file access.

## Architecture
*   **Language:** Node.js (TypeScript)
*   **Core Dependency:** `@modelcontextprotocol/sdk`
*   **Entry Point:** `src/index.ts` (compiled to `dist/index.js`)
*   **Data Source:** Local `docs/` directory (populated via git sparse checkout).

## Building and Running

### Prerequisites
*   Node.js 18+
*   Git

### Installation
1.  **Install dependencies:**
    ```bash
    npm install
    ```
2.  **Build:**
    ```bash
    npm run build
    ```

### Execution
*   **Direct execution:**
    ```bash
    export KLIPPER_DOCS_PATH=./docs
    npm start
    ```

### Client Configuration
To use this with an MCP client (like Claude Desktop), configure it as follows:
```json
{
  "mcpServers": {
    "klipper-docs": {
      "command": "node",
      "args": ["/path/to/klipper-docs-mcp/dist/index.js"],
      "env": {
        "KLIPPER_DOCS_PATH": "/path/to/docs"
      }
    }
  }
}
```

## Development Conventions

### Testing
*   **Framework:** `vitest`
*   **Run tests:**
    ```bash
    npm test
    ```

### Code Structure
*   `src/index.ts`: Main server implementation containing tool definitions.
*   `src/services/`: Service logic (Search, Git, Storage).
*   `docs/`: Directory containing the markdown documentation files.
*   `tests/`: Contains unit tests.

### Environment Variables
*   `KLIPPER_DOCS_PATH`: Path to the directory containing documentation files (default: `./docs`).