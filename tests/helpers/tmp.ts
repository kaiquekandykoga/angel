import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach } from "vitest";

/** Creates a fresh temporary directory per test and chdir's into it. */
export function useTemporaryDirectory(): { readonly path: string } {
  const state = { path: "" };
  let previousCwd = "";

  beforeEach(() => {
    previousCwd = process.cwd();
    state.path = mkdtempSync(join(tmpdir(), "angel-"));
    process.chdir(state.path);
  });

  afterEach(() => {
    process.chdir(previousCwd);
    rmSync(state.path, { recursive: true, force: true });
  });

  return state;
}
