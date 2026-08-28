import { describe, expect, it } from "vitest";
import type { Finding } from "../../apps/server/index.js";
import { gradeIssueReview, gradePrReview, parseAgents } from "../../eval/run.js";

const FINDING: Finding = {
  severity: "major",
  title: "a finding",
  detail: "a detail",
  file: "src/users.ts",
  line: 2,
};

const DIFF = "--- a/src/users.ts\n+++ b/src/users.ts\n@@ -1,1 +1,2 @@\n+const a = 1;\n";

function scoresOf(scores: readonly { name: string; value: number }[]) {
  return Object.fromEntries(scores.map((score) => [score.name, score.value]));
}

describe("parseAgents", () => {
  it("runs every agent when none is named", () => {
    expect(parseAgents([])).toEqual(["pr_review", "issue_review"]);
  });

  it("runs only the named agent", () => {
    expect(parseAgents(["issue_review"])).toEqual(["issue_review"]);
  });

  it("rejects an unknown agent", () => {
    expect(() => parseAgents(["chat"])).toThrow(/Unknown agent: chat/);
  });
});

describe("gradePrReview", () => {
  it("scores citations, expectations, lens coverage, and the finding count", async () => {
    const scores = await gradePrReview({
      input: {
        repository: "angel-eval/shop",
        number: 1,
        title: "a pull request",
        body: "a body",
        headSha: "sha-1",
        diff: DIFF,
        comments: [],
      },
      output: {
        body: "### Security\n\nSQL injection via string concatenation.",
        findings: [FINDING],
        lenses: [],
      },
      expectedOutput: { files: ["src/users.ts"], keywords: ["injection"] },
    });

    expect(scoresOf(scores)).toEqual({
      cited_files_in_diff: 1,
      cited_lines_in_hunks: 1,
      expected_files_flagged: 1,
      expected_keywords_mentioned: 1,
      lenses_covered: 1 / 3,
      finding_count: 1,
    });
  });
});

describe("gradeIssueReview", () => {
  it("scores keywords, acceptance criteria, and the suggested approach", async () => {
    const scores = await gradeIssueReview({
      output: {
        body: "Nothing here is measurable.",
        findings: [],
        output: {
          summary: "a summary",
          findings: [],
          acceptanceCriteria: ["one"],
          suggestedApproach: "",
        },
      },
      expectedOutput: { files: [], keywords: ["measur", "latency"] },
    });

    expect(scoresOf(scores)).toEqual({
      expected_keywords_mentioned: 0.5,
      acceptance_criteria_count: 1,
      suggested_approach_present: 0,
      finding_count: 0,
    });
  });
});
