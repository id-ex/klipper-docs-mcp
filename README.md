# Klipper Docs MCP Server (Node.js)

An MCP server that provides local access to Klipper 3D printer documentation, optimized for low-resource environments.

## Features
*   **Local Search:** Fast search through documentation using filenames, headings, and content.
*   **Git Sync:** Keeps documentation up-to-date with official repositories (Klipper & Moonraker).
*   **Low Resource Usage:** Efficient streaming and reading suitable for Raspberry Pi.

## Installation

### From Source
1.  Clone the repository.
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Build the project:
    ```bash
    npm run build
    ```

### From npm (Coming soon)
```bash
npx klipper-docs-mcp
```

## Usage

### Running the Server
You can run the server directly:

```bash
npm start
```

Or using the built executable:

```bash
./dist/index.js
```

### Configuration
The server uses the `KLIPPER_DOCS_PATH` environment variable to locate documentation.
Default: `./docs`

```bash
export KLIPPER_DOCS_PATH=/path/to/docs
npm start
```

### Claude Desktop Configuration
Add this to your `claude_desktop_config.json`:

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

## Development

*   **Run in dev mode:** `npm run dev`
*   **Run tests:** `npm test`
*   **Build:** `npm run build`

## License
MIT