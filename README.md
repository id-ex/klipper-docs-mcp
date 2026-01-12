# Klipper Docs MCP Server

An MCP server that provides local access to Klipper 3D printer documentation, optimized for low-resource environments.

## Features
*   **Local Search:** Fast search through documentation using filenames, headings, and content.
*   **Git Sync:** Keeps documentation up-to-date with official repositories (Klipper & Moonraker).

## Installation

### Quick Start (npx)
You can run the server directly without installation using `npx`:

```bash
npx klipper-docs-mcp
```

This command will download and run the latest version of the server. By default, it will look for documentation in the `./docs` directory relative to where you run the command. You can override this with the `KLIPPER_DOCS_PATH` environment variable.

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

## CLI Configuration (One-Liner)

### Claude Code
Add the server to your current project configuration in one command:

```bash
claude mcp add klipper-docs -- npx -y klipper-docs-mcp
```

### Gemini CLI
Add the server extension:

```bash
gemini mcp add klipper-docs -- npx -y klipper-docs-mcp
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

## License
MIT
