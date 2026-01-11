import fs from "node:fs/promises";
import path from "node:path";
import { DOCS_DIR, MAX_FILE_CHARS, SUPPORTED_EXTENSIONS } from "../config.js";
import {
  DocumentationNotAvailableError,
  InvalidPathError,
  PathTraversalError,
  ResourceNotFoundError,
} from "../errors.js";

export class StorageManager {
  private docsDir: string;

  constructor(docsDir: string = DOCS_DIR) {
    this.docsDir = docsDir;
  }

  getDocsDir(): string {
    return this.docsDir;
  }

  async isAvailable(): Promise<boolean> {
    try {
      const stats = await fs.stat(this.docsDir);
      return stats.isDirectory();
    } catch {
      return false;
    }
  }

  async requireAvailable(): Promise<void> {
    if (!(await this.isAvailable())) {
      throw new DocumentationNotAvailableError();
    }
  }

  validatePath(relativePath: string): string {
    const targetPath = path.resolve(this.docsDir, relativePath);

    // Ensure the path starts with docsDir
    if (!targetPath.startsWith(this.docsDir)) {
      throw new PathTraversalError(relativePath);
    }

    return targetPath;
  }

  async readFile(
    relativePath: string,
    offset: number = 0,
    limit: number = MAX_FILE_CHARS
  ): Promise<{ content: string; totalChars: number }> {
    await this.requireAvailable();

    const targetPath = this.validatePath(relativePath);

    try {
      const contentBuffer = await fs.readFile(targetPath, "utf-8");
      // Normalize line endings if needed, but simple read is usually fine
      const content = contentBuffer.toString();
      const totalChars = content.length;
      const end = offset + limit;
      const contentSlice = content.slice(offset, end);

      return { content: contentSlice, totalChars };
    } catch (error: any) {
      if (error.code === "ENOENT") {
        throw new ResourceNotFoundError(relativePath);
      }
      throw new InvalidPathError(relativePath, error.message);
    }
  }

  async listFiles(): Promise<string[]> {
    await this.requireAvailable();
    const files: string[] = [];

    async function traverse(dir: string, baseDir: string) {
      const entries = await fs.readdir(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          await traverse(fullPath, baseDir);
        } else if (entry.isFile()) {
           const ext = path.extname(entry.name);
           if (SUPPORTED_EXTENSIONS.includes(ext)) {
               files.push(path.relative(baseDir, fullPath));
           }
        }
      }
    }

    await traverse(this.docsDir, this.docsDir);
    return files;
  }

  async buildTree(currentPath: string = this.docsDir, prefix: string = ""): Promise<string[]> {
    if (!(await this.isAvailable())) {
       return [];
    }

    const lines: string[] = [];
    let entries;
    
    try {
        entries = await fs.readdir(currentPath, { withFileTypes: true });
    } catch (e) {
        return lines;
    }

    // Sort: directories first, then files (case insensitive)
    entries.sort((a, b) => {
        if (a.isDirectory() && !b.isDirectory()) return -1;
        if (!a.isDirectory() && b.isDirectory()) return 1;
        return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
    });
    
    // Filter hidden files
    entries = entries.filter(e => !e.name.startsWith('.'));

    for (let i = 0; i < entries.length; i++) {
        const entry = entries[i];
        const isLastEntry = i === entries.length - 1;
        const connector = isLastEntry ? "└── " : "├── ";
        
        if (entry.isDirectory()) {
            lines.push(`${prefix}${connector}${entry.name}/`);
            const extension = isLastEntry ? "    " : "│   ";
            const subLines = await this.buildTree(path.join(currentPath, entry.name), prefix + extension);
            lines.push(...subLines);
        } else {
             lines.push(`${prefix}${connector}${entry.name}`);
        }
    }
    return lines;
  }
}
