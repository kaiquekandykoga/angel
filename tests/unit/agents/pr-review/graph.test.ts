import { describe, expect, it } from "vitest";
import { buildPrReviewGraph } from "../../../../src/agents/pr-review/graph.js";
import { reviewMarker } from "../../../../src/agents/shared.js";
import type { PullRequest } from "../../../../src/clients/github.js";
import { FakeGitHubClient } from "../../../helpers/github.js";
import { FakeLlmClient } from "../../../helpers/llm.js";
import { useLogCapture } from "../../../helpers/logs.js";

const REPOSITORY = "monalisa/hello-world";
const BOT = "kandy-angel[bot]";

function pullRequest(overrides: Partial<PullRequest> = {}): PullRequest {
  return {
    repository: REPOSITORY,
    number: 1,
    title: "a pr",
    body: "a body",
    headSha: "sha-1",
    ...overrides,
  };
}

function labeled(...pullRequests: PullRequest[]): FakeGitHubClient {
  const github = new FakeGitHubClient();
  github.pullRequests = { [REPOSITORY]: pullRequests };
  for (const each of pullRequests) {
    github.label(each, "angel");
  }
  return github;
}

const run = (client: FakeLlmClient, github: FakeGitHubClient) =>
  buildPrReviewGraph(client, github).invoke({
    pullRequests: [],
    reviews: [],
    failures: [],
  });

describe("buildPrReviewGraph", () => {
  const logs = useLogCapture();

  it("fetches, reviews and posts in one pass", async () => {
    const github = labeled(pullRequest());

    const result = await run(new FakeLlmClient(), github);

    expect(result.reviews).toHaveLength(1);
    expect(github.postedComments).toHaveLength(1);
    expect(github.postedComments[0]?.[1]).toContain(reviewMarker("sha-1"));
  });

  it("posts nothing when nothing is due", async () => {
    const github = new FakeGitHubClient();

    const result = await run(new FakeLlmClient(), github);

    expect(result.reviews).toEqual([]);
    expect(github.postedComments).toEqual([]);
  });

  it("accumulates failures from every node rather than clobbering them", async () => {
    const github = labeled(pullRequest({ number: 1 }), pullRequest({ number: 2 }));
    github.pullRequests["monalisa/broken"] = [];
    github.ensureLabel = async (repository) => {
      if (repository === "monalisa/broken") {
        throw new Error("403");
      }
    };
    const client = new FakeLlmClient();
    client.failStructuredCall = 1;

    const result = await run(client, github);

    expect(result.failures.map((each) => each.stage).sort()).toEqual([
      "fetch_pull_requests",
      "review_pull_requests",
    ]);
    expect(result.reviews).toHaveLength(1);
  });

  it("honours an overridden reviewer login and label", async () => {
    const github = new FakeGitHubClient();
    const target = pullRequest();
    github.pullRequests = { [REPOSITORY]: [target] };
    github.label(target, "look-here");

    const result = await buildPrReviewGraph(new FakeLlmClient(), github, {
      reviewerLogin: "other-bot",
      label: "look-here",
      labelColor: "ffffff",
    }).invoke({ pullRequests: [], reviews: [], failures: [] });

    expect(result.reviews).toHaveLength(1);
    expect(github.ensureLabelCalls).toEqual([[REPOSITORY, "look-here", "ffffff"]]);
  });

  it("logs the wiring and that the graph is ready", () => {
    buildPrReviewGraph(new FakeLlmClient(), new FakeGitHubClient());

    expect(logs.contextOf("wiring pr_review graph nodes")).toEqual({
      reviewer_login: BOT,
      label: "angel",
    });
    expect(logs.withMessage("pr_review graph ready")).toHaveLength(1);
  });
});
