#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import path from "node:path";
import { z } from "zod";
import { DOCS_DIR, MAX_FILE_CHARS, SYNC_DESCRIPTION } from "./config.js";
import { GitManager } from "./services/GitManager.js";
import { SearchEngine } from "./services/SearchEngine.js";
import { StorageManager } from "./services/StorageManager.js";

// Initialize services
const storageManager = new StorageManager();
const gitManager = new GitManager();
const searchEngine = new SearchEngine(DOCS_DIR);

// Create server instance
const server = new McpServer({
  name: "klipper-docs-server",
  version: "0.1.0",
});

let docsOutdated = false;

// Helper to check updates on startup
async function checkUpdates() {
  docsOutdated = await gitManager.checkIfOutdated();
}

// --- Resources ---

server.resource(
  "list-files",
  "file:///list",
  async (uri) => {
    if (!(await storageManager.isAvailable())) {
      return {
        contents: [],
      };
    }

    const files = await storageManager.listFiles();
    return {
      contents: files.map(f => ({
        uri: `file:///${f}`,
        text: `Klipper documentation: ${f}`,
      })),
    };
  }
);

// We can also register dynamic resources for files, 
// but the SDK pattern for reading specific files is often via Tools or generic resource templates.
// The Python version used `app.read_resource` which handles any file:// URI.
// In Node SDK `server.resource` takes a fixed URI or a pattern.
// Let's use a pattern for reading docs.
server.resource(
  "read-doc-file",
  "file:///{path}",
  async (uri) => {
    // Manually extract path from the URI
    const pathStr = uri.href.replace(/^file:\/\/\//, "");
    
    try {
        const { content } = await storageManager.readFile(pathStr);
        return {
            contents: [{
                uri: uri.href,
                text: content
            }]
        };
    } catch (e: any) {
        throw new Error(`Failed to read resource: ${e.message}`);
    }
  }
);


// --- Tools ---

server.tool(
  "search_docs",
  "Search Klipper documentation by query. Returns up to 7 results with file paths and snippets. Matches in filenames and headings are ranked higher.",
  {
    query: z.string().describe("Search query - searches through filenames and document content"),
  },
  async ({ query }) => {
    try {
      const results = await searchEngine.search(query);
      const formatted = searchEngine.formatResults(results);
      return {
        content: [{ type: "text", text: formatted }],
      };
    } catch (error: any) {
      return {
        content: [{ type: "text", text: `Error: ${error.message}` }],
      };
    }
  }
);

server.tool(
  "read_doc",
  `Read a Klipper documentation file. Returns up to ${MAX_FILE_CHARS} characters by default. Use offset and limit for pagination.`, 
  {
    path: z.string().describe("Relative path to the documentation file (e.g., 'Config_Reference.md' or 'prints/bed_mesh.md')"),
    offset: z.number().optional().default(0).describe("Character offset to start reading from (default: 0)"),
    limit: z.number().optional().default(MAX_FILE_CHARS).describe(`Number of characters to read (default: ${MAX_FILE_CHARS})`),
  },
  async ({ path, offset, limit }) => {
    try {
      const { content, totalChars } = await storageManager.readFile(path, offset, limit);
      const end = offset + limit;
      
      let output = content;
      if (offset > 0 || end < totalChars) {
        output += `\n\n[... Showing characters ${offset}-${Math.min(end, totalChars)} of ${totalChars} total]`;
      }

      return {
        content: [{ type: "text", text: output }],
      };
    } catch (error: any) {
      return {
        content: [{ type: "text", text: `Error: ${error.message}` }],
      };
    }
  }
);

server.tool(
  "list_docs_map",
  "List the complete structure of Klipper documentation as a tree. Useful for discovering available files and understanding the docs organization.",
  {},
  async () => {
    if (!(await storageManager.isAvailable())) {
      return {
        content: [{ type: "text", text: "Documentation directory not found. Run sync_docs() first." }],
      };
    }

    const rootName = path.basename(storageManager.getDocsDir());
    const treeLines = await storageManager.buildTree();
    const output = [`${rootName}/`, ...treeLines].join("\n");

    return {
      content: [{ type: "text", text: output }],
    };
  }
);

server.tool(
  "sync_docs",
  docsOutdated ? `${SYNC_DESCRIPTION} (RECOMMENDED: database outdated)` : SYNC_DESCRIPTION,
  {},
  async () => {
    const outputLines: string[] = [];
    const results = await gitManager.syncAll();

    for (const result of results) {
      outputLines.push(`\n--- Syncing ${result.repoName} ---`);
      if (result.success) {
        if (result.wasCloned) {
          outputLines.push(`Cloning ${result.repoName}...`);
        } else if (result.wasUpdated) {
          outputLines.push(`Updating ${result.repoName}...`);
        }
        outputLines.push(result.message);
      } else {
        outputLines.push(result.message);
      }
    }

    // Re-check status
    docsOutdated = await gitManager.checkIfOutdated();
    if (!docsOutdated) {
      outputLines.push("\nAll documentation repositories are up to date.");
    }

    return {
      content: [{ type: "text", text: outputLines.join("\n") }],
    };
  }
);

async function main() {
  await checkUpdates();
  
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Klipper Docs MCP Server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
