import path from "node:path";
import process from "node:process";

// Repository configurations
export const REPOSITORIES = {
  klipper: {
    url: "https://github.com/Klipper3d/klipper.git",
    sparse_path: "docs/",
  },
  moonraker: {
    url: "https://github.com/Arksine/moonraker.git",
    sparse_path: "docs/",
  },
} as const;

// Documentation directory
// Defaulting to ./docs relative to current working directory
export const DOCS_DIR = path.resolve(process.env.KLIPPER_DOCS_PATH || "./docs");

// File reading limits
export const MAX_FILE_CHARS = 10000;
export const SNIPPET_LENGTH = 200;
export const MAX_SEARCH_RESULTS = 7;

// Tool descriptions
export const SYNC_DESCRIPTION = "Sync documentation (Klipper, Moonraker) with remote repositories";

// Git Configuration
export const GIT_CONFIG = {
  clone_timeout: 300_000, // ms
  fetch_timeout: 60_000,  // ms
  rev_parse_timeout: 10_000 // ms
};

// Storage Configuration
export const SUPPORTED_EXTENSIONS = [".md", ".txt"];
