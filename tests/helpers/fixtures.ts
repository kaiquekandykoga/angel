import { readFileSync } from "node:fs";
import { dirname, extname, join } from "node:path";
import { fileURLToPath } from "node:url";

const FIXTURES = join(dirname(fileURLToPath(import.meta.url)), "..", "fixtures");

/** Loads a recorded GitHub payload; `.json` is parsed, anything else is text. */
export function loadFixture<T = unknown>(name: string): T {
  const path = join(FIXTURES, name);
  const text = readFileSync(path, "utf8");
  return (extname(path) === ".json" ? JSON.parse(text) : text) as T;
}
