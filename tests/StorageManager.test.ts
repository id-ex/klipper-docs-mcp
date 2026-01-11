import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { StorageManager } from "../src/services/StorageManager.js";
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";

describe("StorageManager", () => {
  let tmpDir: string;
  let storageManager: StorageManager;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "klipper-docs-test-"));
    await fs.writeFile(path.join(tmpDir, "test.md"), "# Test Content\nHello world");
    await fs.mkdir(path.join(tmpDir, "subdir"));
    await fs.writeFile(path.join(tmpDir, "subdir", "sub.txt"), "Sub content");
    
    storageManager = new StorageManager(tmpDir);
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("should list files", async () => {
    const files = await storageManager.listFiles();
    expect(files).toContain("test.md");
    expect(files).toContain(path.join("subdir", "sub.txt"));
  });

  it("should read file content", async () => {
    const { content } = await storageManager.readFile("test.md");
    expect(content).toContain("Hello world");
  });

  it("should prevent path traversal", async () => {
    await expect(storageManager.readFile("../outside.txt")).rejects.toThrow();
  });
});
