import { describe, expect, it } from "vitest";
import {
  fetchIssues,
  reviewIssues,
} from "../../../../../apps/server/agents/issue-review/nodes.js";
import { REVIEW_SYSTEM_PROMPT } from "../../../../../apps/server/agents/issue-review/prompts.js";
import type { IssueContext } from "../../../../../apps/server/agents/issue-review/state.js";
import type { Comment, Issue } from "../../../../../apps/server/clients/github.js";
import { FakeGitHubClient } from "../../../../helpers/github.js";
import { FakeLlmClient } from "../../../../helpers/llm.js";
import { useLogCapture } from "../../../../helpers/logs.js";

const REPOSITORY = "monalisa/hello-world";
const BOT = "kandy-angel[bot]";

function issue(overrides: Partial<Issue> = {}): Issue {
  return {
    repository: REPOSITORY,
    number: 1,
    title: "an issue",
    body: "a body",
    updatedAt: "2026-08-10T00:00:00Z",
    ...overrides,
  };
}

function comment(overrides: Partial<Comment> = {}): Comment {
  return {
    author: BOT,
    body: "a review",
    createdAt: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

function withLabeled(...issues: Issue[]): FakeGitHubClient {
  const github = new FakeGitHubClient();
  github.issues = { [REPOSITORY]: issues };
  for (const each of issues) {
    github.label(each, "angel");
  }
  return github;
}

const fetch = (github: FakeGitHubClient) => fetchIssues(github, BOT, "angel", "f709c2");

describe("fetchIssues", () => {
  const logs = useLogCapture();

  it("selects an issue the bot never commented on", async () => {
    const result = await fetch(withLabeled(issue()))();

    expect(result.issues.map((each) => each.issue.number)).toEqual([1]);
    expect(logs.contextOf("evaluated issue")).toMatchObject({
      selected: true,
      reason: "never reviewed",
    });
  });

  it("skips an unlabeled issue", async () => {
    const github = new FakeGitHubClient();
    github.issues = { [REPOSITORY]: [issue()] };

    await expect(fetch(github)()).resolves.toMatchObject({ issues: [] });
  });

  it("selects an issue updated since the last review", async () => {
    const target = issue({ updatedAt: "2026-08-20T00:00:00Z" });
    const github = withLabeled(target);
    github.setComments(target, [comment({ createdAt: "2026-08-15T00:00:00Z" })]);

    const result = await fetch(github)();

    expect(result.issues).toHaveLength(1);
    expect(logs.contextOf("evaluated issue")).toMatchObject({
      reason: "updated since last review",
    });
  });

  it("skips an issue untouched since the last review", async () => {
    const target = issue({ updatedAt: "2026-08-10T00:00:00Z" });
    const github = withLabeled(target);
    github.setComments(target, [comment({ createdAt: "2026-08-15T00:00:00Z" })]);

    const result = await fetch(github)();

    expect(result.issues).toEqual([]);
    expect(logs.contextOf("evaluated issue")).toMatchObject({
      reason: "already up to date",
    });
  });

  it("ignores comments by anyone but the bot", async () => {
    const target = issue();
    const github = withLabeled(target);
    github.setComments(target, [
      comment({ author: "monalisa", createdAt: "2026-09-01T00:00:00Z" }),
    ]);

    await expect(fetch(github)()).resolves.toMatchObject({
      issues: [expect.anything()],
    });
  });

  it("ensures the label before listing on every repository", async () => {
    const github = withLabeled(issue());
    github.issues["monalisa/other"] = [];

    await fetch(github)();

    expect(github.ensureLabelCalls).toEqual([
      [REPOSITORY, "angel", "f709c2"],
      ["monalisa/other", "angel", "f709c2"],
    ]);
    expect(github.callLog[0]).toEqual(["ensureLabel", REPOSITORY]);
  });

  it("records a repository-level failure and keeps scanning", async () => {
    const github = withLabeled(issue());
    github.issues["monalisa/broken"] = [];
    github.ensureLabel = async (repository) => {
      if (repository === "monalisa/broken") {
        throw new Error("403");
      }
    };

    const result = await fetch(github)();

    expect(result.failures).toEqual([
      {
        repository: "monalisa/broken",
        number: 0,
        stage: "fetch_issues",
        errorType: "Error",
        error: "403",
      },
    ]);
    expect(result.issues).toHaveLength(1);
  });

  it("records an item-level failure and keeps scanning the repository", async () => {
    const github = withLabeled(issue({ number: 1 }), issue({ number: 2 }));
    github.listComments = async (target) => {
      if (target.number === 1) {
        throw new Error("500");
      }
      return [];
    };

    const result = await fetch(github)();

    expect(result.failures).toMatchObject([{ number: 1, stage: "fetch_issues" }]);
    expect(result.issues.map((each) => each.issue.number)).toEqual([2]);
  });

  it("logs how much it scanned and how much is due", async () => {
    await fetch(withLabeled(issue(), issue({ number: 2 })))();

    expect(logs.contextOf("issues fetched")).toEqual({
      repositories_scanned: 1,
      items_scanned: 2,
      items_due_for_review: 2,
    });
  });
});

describe("reviewIssues", () => {
  const logs = useLogCapture();

  function context(overrides: Partial<Issue> = {}): IssueContext {
    return { issue: issue(overrides), comments: [] };
  }

  it("calls the model once per issue", async () => {
    const client = new FakeLlmClient();

    await reviewIssues(client)({
      issues: [context({ number: 1 }), context({ number: 2 })],
    });

    expect(client.calls).toHaveLength(2);
  });

  it("sends the issue review system prompt", async () => {
    const client = new FakeLlmClient();

    await reviewIssues(client)({ issues: [context()] });

    expect(client.lastCall[0]?.content).toBe(REVIEW_SYSTEM_PROMPT);
  });

  it("puts the title, body and comments in the human message", async () => {
    const client = new FakeLlmClient();

    await reviewIssues(client)({
      issues: [
        { issue: issue(), comments: [comment({ author: "octocat", body: "hi" })] },
      ],
    });

    const [, human] = client.lastCall;
    expect(human?.content).toContain("an issue");
    expect(human?.content).toContain("a body");
    expect(human?.content).toContain("@octocat: hi");
  });

  it("renders the acceptance criteria and suggested approach", async () => {
    const client = new FakeLlmClient();
    client.structuredReply = {
      summary: "a summary",
      findings: [],
      acceptanceCriteria: ["one"],
      suggestedApproach: "do it",
    };

    const result = await reviewIssues(client)({ issues: [context()] });

    const body = result.reviews[0]?.body ?? "";
    expect(body).toContain("### Acceptance criteria\n\n- one");
    expect(body).toContain("### Suggested approach\n\ndo it");
  });

  it("writes no head-sha marker", async () => {
    const client = new FakeLlmClient();

    const result = await reviewIssues(client)({ issues: [context()] });

    expect(result.reviews[0]?.body).not.toContain("<!-- angel: sha=");
  });

  it("keeps reviewing after one issue fails", async () => {
    const client = new FakeLlmClient();
    client.failStructuredCall = 1;

    const result = await reviewIssues(client)({
      issues: [context({ number: 1 }), context({ number: 2 })],
    });

    expect(result.reviews.map((each) => each.target.number)).toEqual([2]);
    expect(result.failures).toMatchObject([
      { number: 1, stage: "review_issues", error: "llm exploded" },
    ]);
  });

  it("logs one review-produced record with no lens", async () => {
    const client = new FakeLlmClient();

    await reviewIssues(client)({ issues: [context()] });

    const records = logs.withMessage("review produced");
    expect(records).toHaveLength(1);
    expect(records[0]?.context).not.toHaveProperty("lens");
  });
});
