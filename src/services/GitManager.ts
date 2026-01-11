import { execFile } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";
import { DOCS_DIR, GIT_CONFIG, REPOSITORIES } from "../config.js";
import { GitOperationError } from "../errors.js";

const execFileAsync = promisify(execFile);

export interface SyncResult {
  repoName: string;
  success: boolean;
  message: string;
  wasCloned: boolean;
  wasUpdated: boolean;
}

export class GitManager {
  private docsDir: string;
  private repositories: typeof REPOSITORIES;

  constructor() {
    this.docsDir = DOCS_DIR;
    this.repositories = REPOSITORIES;
  }

  private async runGitCommand(
    args: string[],
    cwd: string,
    timeout: number
  ): Promise<{ stdout: string; stderr: string }> {
    try {
      return await execFileAsync("git", args, {
        cwd,
        timeout,
        encoding: "utf-8",
      });
    } catch (error: any) {
      // execFile throws on non-zero exit code
      // We want to capture stderr and throw our own error or return it for handling
      throw error;
    }
  }

  async syncAll(): Promise<SyncResult[]> {
    // Ensure docs directory exists
    try {
      await fs.mkdir(this.docsDir, { recursive: true });
    } catch (error) {
      // Ignore if exists
    }

    const results: SyncResult[] = [];
    for (const [name, config] of Object.entries(this.repositories)) {
      results.push(await this.syncRepository(name, config));
    }
    return results;
  }

  private async syncRepository(name: string, config: { url: string; sparse_path: string }): Promise<SyncResult> {
    const repoDir = path.join(this.docsDir, name);
    
    try {
        const stats = await fs.stat(repoDir).catch(() => null);
        if (!stats) {
            return await this.cloneRepository(name, repoDir, config.url, config.sparse_path);
        } else {
            return await this.updateRepository(name, repoDir);
        }
    } catch (error: any) {
        return {
            repoName: name,
            success: false,
            message: `Error: ${error.message || error}`,
            wasCloned: false,
            wasUpdated: false,
        };
    }
  }

  private async cloneRepository(
    name: string,
    repoDir: string,
    url: string,
    sparsePath: string
  ): Promise<SyncResult> {
    try {
      const parentDir = path.dirname(repoDir);
      
      // Clone command
      const cloneArgs = sparsePath
        ? ["clone", "--depth=1", "--no-checkout", url, repoDir]
        : ["clone", "--depth=1", url, repoDir];

      await this.runGitCommand(cloneArgs, parentDir, GIT_CONFIG.clone_timeout);

      // Sparse checkout config
      if (sparsePath) {
        await this.runGitCommand(
          ["config", "core.sparseCheckout", "true"],
          repoDir,
          GIT_CONFIG.rev_parse_timeout
        );
        await this.runGitCommand(
          ["sparse-checkout", "set", sparsePath],
          repoDir,
          GIT_CONFIG.rev_parse_timeout
        );
        await this.runGitCommand(
          ["checkout"],
          repoDir,
          GIT_CONFIG.rev_parse_timeout
        );
      }

      return {
        repoName: name,
        success: true,
        message: "Successfully cloned.",
        wasCloned: true,
        wasUpdated: false,
      };
    } catch (error: any) {
       return {
            repoName: name,
            success: false,
            message: `Clone failed:\n${error.stderr || error.message}`,
            wasCloned: false,
            wasUpdated: false,
        };
    }
  }

  private async updateRepository(name: string, repoDir: string): Promise<SyncResult> {
    try {
      const result = await this.runGitCommand(
        ["pull", "--depth=1"],
        repoDir,
        GIT_CONFIG.clone_timeout
      );
      
      const output = result.stdout.trim() || "Already up to date.";
      
      return {
        repoName: name,
        success: true,
        message: output,
        wasCloned: false,
        wasUpdated: true,
      };
    } catch (error: any) {
       return {
            repoName: name,
            success: false,
            message: `Update failed:\n${error.stderr || error.message}`,
            wasCloned: false,
            wasUpdated: false,
        };
    }
  }

  async checkIfOutdated(): Promise<boolean> {
    try {
       const stats = await fs.stat(this.docsDir).catch(() => null);
       if (!stats) return false;

       for (const name of Object.keys(this.repositories)) {
           const repoDir = path.join(this.docsDir, name);
           const repoStats = await fs.stat(repoDir).catch(() => null);
           if (!repoStats) continue;
           
           try {
               await this.runGitCommand(["fetch"], repoDir, GIT_CONFIG.fetch_timeout);
               
               const localRev = await this.runGitCommand(["rev-parse", "HEAD"], repoDir, GIT_CONFIG.rev_parse_timeout);
               const remoteRev = await this.runGitCommand(["rev-parse", "@{u}"], repoDir, GIT_CONFIG.rev_parse_timeout);
               
               if (localRev.stdout.trim() !== remoteRev.stdout.trim()) {
                   return true;
               }
           } catch {
               continue;
           }
       }
    } catch {
        return false;
    }
    return false;
  }
}
