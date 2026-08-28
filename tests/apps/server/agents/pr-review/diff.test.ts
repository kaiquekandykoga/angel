import { describe, expect, it } from "vitest";
import {
  filterDiff,
  MAX_FILE_BYTES,
  renderOmissions,
  splitDiff,
} from "../../../../../apps/server/agents/pr-review/diff.js";
import { loadFixture } from "../../../../helpers/fixtures.js";

const MIXED = loadFixture<string>("github/mixed.diff");

function fileDiff(path: string, lines: number): string {
  const body = Array.from({ length: lines }, (_, index) => `+line ${index}`).join("\n");
  return `diff --git a/${path} b/${path}\n--- a/${path}\n+++ b/${path}\n@@ -0,0 +1 @@\n${body}\n`;
}

describe("splitDiff", () => {
  it("splits on file headers and keeps the new path", () => {
    expect(splitDiff(MIXED).map((each) => each.path)).toEqual([
      "src/greet.ts",
      "package-lock.json",
      "dist/bundle.js",
      "docs/logo.png",
      "web/app.min.js",
    ]);
  });

  it("keeps text carrying no file header as one chunk", () => {
    expect(splitDiff("just some text").map((each) => each.path)).toEqual([""]);
  });

  it("drops an empty diff", () => {
    expect(splitDiff("")).toEqual([]);
  });
});

describe("filterDiff", () => {
  it("keeps source files and drops generated, vendored, and binary ones", () => {
    const filtered = filterDiff(MIXED);

    expect(filtered.text).toContain("src/greet.ts");
    expect(filtered.includedFiles).toBe(1);
    expect(filtered.skipped).toEqual([
      { path: "package-lock.json", reason: "generated or vendored" },
      { path: "dist/bundle.js", reason: "generated or vendored" },
      { path: "docs/logo.png", reason: "binary" },
      { path: "web/app.min.js", reason: "generated or vendored" },
    ]);
  });

  it("drops a single file larger than the per-file cap", () => {
    const filtered = filterDiff(fileDiff("src/big.ts", MAX_FILE_BYTES));

    expect(filtered.text).toBe("");
    expect(filtered.skipped).toEqual([
      { path: "src/big.ts", reason: `larger than ${MAX_FILE_BYTES} bytes` },
    ]);
  });

  it("stops including files once the total budget is exhausted", () => {
    const diff = `${fileDiff("src/a.ts", 10)}${fileDiff("src/b.ts", 10)}`;

    const filtered = filterDiff(diff, 200);

    expect(filtered.includedFiles).toBe(1);
    expect(filtered.bytes).toBeLessThanOrEqual(200);
    expect(filtered.skipped).toEqual([
      { path: "src/b.ts", reason: "diff size budget exhausted" },
    ]);
  });

  it("reports the original size alongside the filtered one", () => {
    const filtered = filterDiff(MIXED);

    expect(filtered.originalBytes).toBe(MIXED.length);
    expect(filtered.bytes).toBeLessThan(filtered.originalBytes);
  });

  it("keeps a diff that needs no filtering whole", () => {
    const diff = fileDiff("src/a.ts", 3);

    expect(filterDiff(diff)).toMatchObject({ text: diff, skipped: [] });
  });
});

describe("renderOmissions", () => {
  it("is empty when nothing was omitted", () => {
    expect(renderOmissions([])).toBe("");
  });

  it("names every omitted file and its reason", () => {
    const marker = renderOmissions(filterDiff(MIXED).skipped);

    expect(marker).toContain("4 file(s) omitted");
    expect(marker).toContain("- package-lock.json (generated or vendored)");
    expect(marker).toContain("- docs/logo.png (binary)");
  });
});
