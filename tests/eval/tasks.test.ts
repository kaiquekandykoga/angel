import { describe, expect, it } from "vitest";
import { reviewMarker } from "../../apps/server/agents/shared.js";
import { PR_REVIEW_ITEMS } from "../../eval/datasets.js";
import { runIssueReview, runPrReview } from "../../eval/tasks.js";
import { FakeLlmClient } from "../helpers/llm.js";

const PULL_REQUEST = {
  repository: "angel-eval/shop",
  number: 7,
  title: "a pull request",
  body: "a body",
  headSha: "sha-7",
  diff: "--- a/src/users.ts\n+++ b/src/users.ts\n@@ -1,1 +1,2 @@\n+const a = 1;\n",
  comments: [],
};

const ISSUE = {
  repository: "angel-eval/shop",
  number: 8,
  title: "an issue",
  body: "a body",
  updatedAt: "2026-08-01T00:00:00Z",
  comments: [],
};

describe("runPrReview", () => {
  it("returns the body the graph would post, one lens output per lens", async () => {
    const client = new FakeLlmClient();

    const result = await runPrReview(PULL_REQUEST, client);

    expect(result.lenses).toHaveLength(3);
    expect(result.findings).toHaveLength(3);
    expect(result.body).toContain("### Security");
    expect(result.body).toContain(reviewMarker("sha-7"));
  });

  it("feeds the case's diff to the model", async () => {
    const client = new FakeLlmClient();
    const [first] = PR_REVIEW_ITEMS;
    if (first === undefined) {
      throw new Error("the pull request dataset is empty");
    }

    await runPrReview(first.input, client);

    expect(client.lastCall.at(-1)?.content).toContain(first.input.diff);
  });

  it("fails loudly when the graph produces no review", async () => {
    const client = new FakeLlmClient();
    client.failStructuredCall = 1;

    await expect(runPrReview(PULL_REQUEST, client)).rejects.toThrow(/llm exploded/);
  });
});

describe("runIssueReview", () => {
  it("returns the rendered review beside the structured output", async () => {
    const client = new FakeLlmClient();
    client.structuredReply = {
      summary: "a summary",
      findings: [],
      acceptanceCriteria: ["one"],
      suggestedApproach: "do the thing",
    };

    const result = await runIssueReview(ISSUE, client);

    expect(result.output.acceptanceCriteria).toEqual(["one"]);
    expect(result.body).toContain("### Acceptance criteria");
  });

  it("fails loudly when the graph produces no review", async () => {
    const client = new FakeLlmClient();
    client.failStructuredCall = 1;

    await expect(runIssueReview(ISSUE, client)).rejects.toThrow(/llm exploded/);
  });
});
