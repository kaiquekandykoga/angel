import { existsSync } from "node:fs";
import { dirname, join, parse } from "node:path";
import { config } from "dotenv";

const loadedDirectories = new Set<string>();

function findDotenv(startDirectory: string): string | undefined {
  const { root } = parse(startDirectory);
  let directory = startDirectory;
  while (true) {
    const candidate = join(directory, ".env");
    if (existsSync(candidate)) {
      return candidate;
    }
    if (directory === root) {
      return undefined;
    }
    directory = dirname(directory);
  }
}

export function loadEnvVar(name: string): string | undefined {
  const cwd = process.cwd();
  if (!loadedDirectories.has(cwd)) {
    loadedDirectories.add(cwd);
    const path = findDotenv(cwd);
    if (path !== undefined) {
      config({ path, override: false, quiet: true });
    }
  }
  return process.env[name];
}

export function resetEnvCache(): void {
  loadedDirectories.clear();
}
