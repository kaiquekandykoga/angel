import { describe, expect, it } from "vitest";
import type { Finding } from "../../apps/server/index.js";
import {
  acceptanceCriteriaCount,
  citedFilesInDiff,
  citedLinesInHunks,
  expectedFilesFlagged,
  expectedKeywordsMentioned,
  findingCount,
  lensesCovered,
  parseDiff,
  suggestedApproachPresent,
} from "../../eval/scorers.js";

const DIFF = `diff --git a/src/users.ts b/src/users.ts
--- a/src/users.ts
+++ b/src/users.ts
@@ -12,6 +12,11 @@ export class UserRepository {
   }
+  const sql = "SELECT";
@@ -40,2 +45 @@
+  const other = 1;
diff --git a/src/gone.ts b/src/gone.ts
--- a/src/gone.ts
+++ /dev/null
@@ -1,3 +0,0 @@
-  const dead = 1;
`;

function finding(overrides: Partial<Finding> = {}): Finding {
  return {
    severity: "major",
    title: "a finding",
    detail: "a detail",
    file: "src/users.ts",
    line: 15,
    ...overrides,
  };
}

describe("parseDiff", () => {
  it("maps each added file to the line ranges its hunks touch", () => {
    expect(parseDiff(DIFF).get("src/users.ts")).toEqual([
      { start: 12, end: 22 },
      { start: 45, end: 45 },
    ]);
  });

  it("skips a file the diff deletes", () => {
    expect([...parseDiff(DIFF).keys()]).toEqual(["src/users.ts"]);
  });

  it("has nothing to say about an empty diff", () => {
    expect(parseDiff("")).toEqual(new Map());
  });
});

describe("citedFilesInDiff", () => {
  it("scores a citation the diff touches", () => {
    expect(citedFilesInDiff([finding()], DIFF)).toEqual([
      {
        name: "cited_files_in_diff",
        value: 1,
        comment: "1 of 1 cited files are touched by the diff",
      },
    ]);
  });

  it("halves the score for one hallucinated path", () => {
    const findings = [finding(), finding({ file: "src/imagined.ts" })];

    expect(citedFilesInDiff(findings, DIFF)[0]?.value).toBe(0.5);
  });

  it("skips the score when no finding cites a file", () => {
    expect(citedFilesInDiff([finding({ file: null })], DIFF)).toEqual([]);
  });
});

describe("citedLinesInHunks", () => {
  it("scores a line inside a changed hunk", () => {
    expect(citedLinesInHunks([finding({ line: 22 })], DIFF)[0]?.value).toBe(1);
  });

  it("fails a line outside every hunk of the cited file", () => {
    expect(citedLinesInHunks([finding({ line: 23 })], DIFF)[0]?.value).toBe(0);
  });

  it("fails a line on a file the diff never touched", () => {
    const scores = citedLinesInHunks([finding({ file: "src/imagined.ts" })], DIFF);

    expect(scores[0]?.value).toBe(0);
  });

  it("skips findings that cite no line", () => {
    expect(citedLinesInHunks([finding({ line: null })], DIFF)).toEqual([]);
  });
});

describe("expectedFilesFlagged", () => {
  it("scores an expected file some finding cites", () => {
    expect(expectedFilesFlagged([finding()], ["src/users.ts"])[0]?.value).toBe(1);
  });

  it("scores an expected file nothing cites", () => {
    expect(expectedFilesFlagged([finding()], ["src/queue.ts"])[0]?.value).toBe(0);
  });

  it("skips the score when the case expects no file", () => {
    expect(expectedFilesFlagged([finding()], [])).toEqual([]);
  });
});

describe("expectedKeywordsMentioned", () => {
  it("matches a stem case-insensitively and names what is missing", () => {
    const scores = expectedKeywordsMentioned("Reproduction steps missing", [
      "reproduc",
      "version",
    ]);

    expect(scores[0]?.value).toBe(0.5);
    expect(scores[0]?.comment).toContain("missing: version");
  });

  it("skips the score when the case expects no keyword", () => {
    expect(expectedKeywordsMentioned("anything", [])).toEqual([]);
  });
});

describe("lensesCovered", () => {
  it("scores the lens sections the rendered body carries", () => {
    const body = "### Security\n\nNo findings.\n\n### Quality\n\nNo findings.";

    expect(lensesCovered(body, ["security", "quality", "performance"])).toEqual([
      {
        name: "lenses_covered",
        value: 2 / 3,
        comment: "2 of 3 lenses have a section in the posted body",
      },
    ]);
  });
});

describe("findingCount", () => {
  it("reports the count rather than a ratio", () => {
    expect(findingCount([finding(), finding()])).toEqual({
      name: "finding_count",
      value: 2,
      comment: "2 findings across the review",
    });
  });
});

describe("the issue review scorers", () => {
  const output = {
    summary: "a summary",
    findings: [],
    acceptanceCriteria: ["one", "two"],
    suggestedApproach: "do the thing",
  };

  it("counts the acceptance criteria", () => {
    expect(acceptanceCriteriaCount(output).value).toBe(2);
  });

  it("scores a suggested approach", () => {
    expect(suggestedApproachPresent(output).value).toBe(1);
  });

  it("scores a blank suggested approach as absent", () => {
    expect(suggestedApproachPresent({ ...output, suggestedApproach: "  " })).toEqual({
      name: "suggested_approach_present",
      value: 0,
      comment: "no approach was suggested",
    });
  });
});
