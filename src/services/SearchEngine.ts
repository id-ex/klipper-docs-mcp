import fs from "node:fs/promises";
import path from "node:path";
import { MAX_SEARCH_RESULTS, SNIPPET_LENGTH, SUPPORTED_EXTENSIONS } from "../config.js";
import {
  DocumentationNotAvailableError,
  SearchQueryEmptyError,
} from "../errors.js";

export interface SearchResult {
  rank: number;
  path: string;
  snippet: string;
}

export class SearchEngine {
  private docsDir: string;

  constructor(docsDir: string) {
    this.docsDir = docsDir;
  }

  private isSupportedFile(filename: string): boolean {
    return SUPPORTED_EXTENSIONS.some((ext) => filename.endsWith(ext));
  }

  private escapeRegExp(string: string): string {
    return string.replace(/[.*+?^${}()|[\\]/g, "\\$& ");
  }

  private extractHeadingMatches(
    content: string,
    query: string
  ): { matches: { start: number; snippet: string }[]; ranges: [number, number][] } {
    const matches: { start: number; snippet: string }[] = [];
    const ranges: [number, number][] = [];
    
    // JS Regex for multiline headings containing query
    // ^(#{1,6}\s.*query.*)$ with 'm' flag for multiline and 'i' for case insensitive
    const escapedQuery = this.escapeRegExp(query);
    const regex = new RegExp(`^(#{1,6}\s.*${escapedQuery}.*)$`, "gmi");

    let match;
    while ((match = regex.exec(content)) !== null) {
      const start = Math.max(0, match.index - 50);
      const end = Math.min(content.length, match.index + match[0].length + 50);
      const snippet = content.slice(start, end).trim();
      
      matches.push({ start: match.index, snippet: "heading" }); // Type marker usually not needed if we just need snippet string, but Python code used it.
                                                                // Wait, Python code returns (start, "heading", snippet)
      // Actually, I'll stick to returning what's needed for logic.
      // Python logic: matches.append((match.start(), "heading", snippet))
      
      matches.push({ start: match.index, snippet });
      ranges.push([match.index, match.index + match[0].length]);
    }

    return { matches, ranges };
  }

  private extractContentMatches(
    content: string,
    query: string,
    headingRanges: [number, number][]
  ): { start: number; snippet: string }[] {
    const matches: { start: number; snippet: string }[] = [];
    const escapedQuery = this.escapeRegExp(query);
    const regex = new RegExp(escapedQuery, "gi");

    let match;
    while ((match = regex.exec(content)) !== null) {
      // Check overlap
      let isHeading = false;
      for (const [hStart, hEnd] of headingRanges) {
        if (match.index >= hStart && match.index + match[0].length <= hEnd) {
          isHeading = true;
          break;
        }
      }

      if (isHeading) continue;

      const start = Math.max(0, match.index - SNIPPET_LENGTH / 2);
      const end = Math.min(content.length, match.index + match[0].length + SNIPPET_LENGTH / 2);
      const snippet = content.slice(start, end).trim();
      
      matches.push({ start: match.index, snippet });
    }

    return matches;
  }

  private determineRank(filenameMatch: boolean, hasHeadingMatches: boolean): number {
    if (filenameMatch) return 1;
    if (hasHeadingMatches) return 2;
    return 3;
  }

  async search(query: string): Promise<SearchResult[]> {
    if (!query) {
      throw new SearchQueryEmptyError();
    }

    try {
      await fs.access(this.docsDir);
    } catch {
      throw new DocumentationNotAvailableError();
    }

    const queryLower = query.toLowerCase();
    const results: SearchResult[] = [];

    // Recursive walk
    const walk = async (dir: string) => {
      const entries = await fs.readdir(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        
        if (entry.isDirectory()) {
          await walk(fullPath);
          continue;
        }

        if (!this.isSupportedFile(entry.name)) continue;

        const relPath = path.relative(this.docsDir, fullPath);
        const filenameMatch = relPath.toLowerCase().includes(queryLower);

        try {
          const content = await fs.readFile(fullPath, "utf-8");
          
          const { matches: headingMatches, ranges: headingRanges } = this.extractHeadingMatches(content, query);
          const contentMatches = this.extractContentMatches(content, query, headingRanges);

          const allMatches = [...headingMatches, ...contentMatches];
          
          if (allMatches.length > 0 || filenameMatch) {
            allMatches.sort((a, b) => a.start - b.start);
            
            const hasHeadingMatches = headingMatches.length > 0;
            const rank = this.determineRank(filenameMatch, hasHeadingMatches);
            
            // Best snippet: first match or start of file
            let snippet = "";
            if (allMatches.length > 0) {
                snippet = allMatches[0].snippet;
            } else {
                snippet = content.slice(0, SNIPPET_LENGTH) + "...";
            }

            results.push({ rank, path: relPath, snippet });
          }

        } catch (e) {
            // Ignore read errors
        }
      }
    };

    await walk(this.docsDir);

    results.sort((a, b) => a.rank - b.rank);
    return results.slice(0, MAX_SEARCH_RESULTS);
  }

  formatResults(results: SearchResult[]): string {
    if (results.length === 0) return "No results found.";
    return results.map(r => `## ${r.path}
${r.snippet}
`).join("\n");
  }
}
