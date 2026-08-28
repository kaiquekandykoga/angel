import { describe, expect, it } from "vitest";
import { buildIssueReviewGraph } from "../../../../../apps/server/agents/issue-review/graph.js";
import type { Issue } from "../../../../../apps/server/external/github/client.js";
import { FakeGitHubClient } from "../../../../helpers/github.js";
import { FakeLlmClient } from "../../../../helpers/llm.js";
import { useLogCapture } from "../../../../helpers/logs.js";

const REPOSITORY = "monalisa/hello-world";

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

function labeled(...issues: Issue[]): FakeGitHubClient {
  const github = new FakeGitHubClient();
  github.issues = { [REPOSITORY]: issues };
  for (const each of issues) {
    github.label(each, "angel");
  }
  return github;
}

const run = (client: FakeLlmClient, github: FakeGitHubClient) =>
  buildIssueReviewGraph(client, github).invoke({
    issues: [],
    reviews: [],
    failures: [],
  });

describe("buildIssueReviewGraph", () => {
  const logs = useLogCapture();

  it("fetches, reviews and posts in one pass", async () => {
    const github = labeled(issue());

    const result = await run(new FakeLlmClient(), github);

    expect(result.reviews).toHaveLength(1);
    expect(github.postedComments).toHaveLength(1);
  });

  it("posts nothing when nothing is due", async () => {
    const github = new FakeGitHubClient();

    const result = await run(new FakeLlmClient(), github);

    expect(result.reviews).toEqual([]);
    expect(github.postedComments).toEqual([]);
  });

  it("accumulates failures from every node rather than clobbering them", async () => {
    const github = labeled(issue({ number: 1 }), issue({ number: 2 }));
    github.issues["monalisa/broken"] = [];
    github.ensureLabel = async (repository) => {
      if (repository === "monalisa/broken") {
        throw new Error("403");
      }
    };
    const client = new FakeLlmClient();
    client.failStructuredCall = 1;

    const result = await run(client, github);

    expect(result.failures.map((each) => each.stage).sort()).toEqual([
      "fetch_issues",
      "review_issues",
    ]);
    expect(result.reviews).toHaveLength(1);
  });

  it("honours an overridden label", async () => {
    const github = new FakeGitHubClient();
    const target = issue();
    github.issues = { [REPOSITORY]: [target] };
    github.label(target, "look-here");

    const result = await buildIssueReviewGraph(new FakeLlmClient(), github, {
      label: "look-here",
      labelColor: "ffffff",
    }).invoke({ issues: [], reviews: [], failures: [] });

    expect(result.reviews).toHaveLength(1);
    expect(github.ensureLabelCalls).toEqual([[REPOSITORY, "look-here", "ffffff"]]);
  });

  it("logs the wiring and that the graph is ready", () => {
    buildIssueReviewGraph(new FakeLlmClient(), new FakeGitHubClient());

    expect(logs.withMessage("issue_review graph ready")).toHaveLength(1);
  });
});
