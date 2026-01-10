# Klipper Docs MCP Server

## Project Overview
This project serves as a Model Context Protocol (MCP) server that provides local access to Klipper 3D printer documentation. It is specifically designed for low-resource environments, such as Raspberry Pi, by avoiding heavy database dependencies and utilizing efficient file-based operations.

**Key Features:**
*   **Local Search:** Performs searches directly on the file system without external APIs.
*   **Resource Efficiency:** Uses streaming and generator patterns to minimize RAM/CPU usage.
*   **Synchronization:** Includes tools to sync with the official Klipper GitHub repository via `git`.
*   **Security:** Implements path traversal protection for file access.

## Architecture
*   **Language:** Python 3.10+
*   **Core Dependency:** `mcp` SDK
*   **Entry Point:** `klipper_docs_mcp/server.py`
*   **Data Source:** Local `docs/` directory (populated via git sparse checkout).

## Building and Running

### Prerequisites
*   Python 3.10 or higher
*   Git

### Installation
1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    Or using `uv`:
    ```bash
    uv pip install -e .
    ```

### Execution
*   **Using the wrapper script:**
    ```bash
    ./run_server.sh
    ```
*   **Direct Python module execution:**
    ```bash
    export KLIPPER_DOCS_PATH=./docs
    python -m klipper_docs_mcp.server
    ```

### Client Configuration
To use this with an MCP client (like Claude Desktop), configure it as follows:
```json
{
  "mcpServers": {
    "klipper-docs": {
      "command": "python",
      "args": ["-m", "klipper_docs_mcp.server"],
      "env": {
        "KLIPPER_DOCS_PATH": "/path/to/docs"
      }
    }
  }
}
```

## Development Conventions

### Testing
*   **Framework:** `pytest`
*   **Run tests:**
    ```bash
    pytest
    ```

### Code Structure
*   `klipper_docs_mcp/server.py`: Main server implementation containing tool definitions:
    *   `search_docs(query)`: Search Klipper documentation.
    *   `read_doc(path, offset=0, limit=10000)`: Read a documentation file with pagination support.
    *   `list_docs_map()`: List documentation structure.
    *   `sync_docs()`: Sync with Klipper GitHub repository.
*   `docs/`: Directory containing the markdown documentation files.
*   `tests/`: Contains unit tests (`test_server.py`).

### Environment Variables
*   `KLIPPER_DOCS_PATH`: Path to the directory containing documentation files (default: `./docs`).
