import { SystemMessage } from "@langchain/core/messages";
import { describe, expect, it } from "vitest";
import {
  fetchPullRequests,
  renderMergedReview,
  reviewPullRequests,
} from "../../../../../apps/server/agents/pr-review/nodes.js";
import { REVIEW_LENSES } from "../../../../../apps/server/agents/pr-review/prompts.js";
import type { PullRequestContext } from "../../../../../apps/server/agents/pr-review/state.js";
import { reviewMarker } from "../../../../../apps/server/agents/shared.js";
import type {
  Comment,
  PullRequest,
} from "../../../../../apps/server/clients/github.js";
import { FakeGitHubClient } from "../../../../helpers/github.js";
import { contentsOf, FakeLlmClient } from "../../../../helpers/llm.js";
import { useLogCapture } from "../../../../helpers/logs.js";

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

function comment(overrides: Partial<Comment> = {}): Comment {
  return {
    author: BOT,
    body: "",
    createdAt: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

function withLabeled(...pullRequests: PullRequest[]): FakeGitHubClient {
  const github = new FakeGitHubClient();
  github.pullRequests = { [REPOSITORY]: pullRequests };
  for (const each of pullRequests) {
    github.label(each, "angel");
  }
  return github;
}

const fetch = (github: FakeGitHubClient) =>
  fetchPullRequests(github, BOT, "angel", "f709c2");

describe("fetchPullRequests", () => {
  const logs = useLogCapture();

  it("selects a pull request the bot never commented on", async () => {
    const github = withLabeled(pullRequest());

    const result = await fetch(github)();

    expect(result.pullRequests.map((each) => each.pullRequest.number)).toEqual([1]);
    expect(logs.contextOf("evaluated pull request")).toMatchObject({
      selected: true,
      reason: "never reviewed",
    });
  });

  it("skips an unlabeled pull request", async () => {
    const github = new FakeGitHubClient();
    github.pullRequests = { [REPOSITORY]: [pullRequest()] };

    const result = await fetch(github)();

    expect(result.pullRequests).toEqual([]);
  });

  it("skips a pull request already reviewed at this head", async () => {
    const target = pullRequest();
    const github = withLabeled(target);
    github.setComments(target, [comment({ body: reviewMarker("sha-1") })]);

    const result = await fetch(github)();

    expect(result.pullRequests).toEqual([]);
    expect(logs.contextOf("evaluated pull request")).toMatchObject({
      selected: false,
      reason: "already up to date",
    });
  });

  it("selects a pull request whose head has moved", async () => {
    const target = pullRequest({ headSha: "sha-2" });
    const github = withLabeled(target);
    github.setComments(target, [comment({ body: reviewMarker("sha-1") })]);

    const result = await fetch(github)();

    expect(result.pullRequests).toHaveLength(1);
    expect(logs.contextOf("evaluated pull request")).toMatchObject({
      reason: "new head",
    });
  });

  it("selects a pull request whose last review recorded no head", async () => {
    const target = pullRequest();
    const github = withLabeled(target);
    github.setComments(target, [comment({ body: "an old review, no marker" })]);

    const result = await fetch(github)();

    expect(result.pullRequests).toHaveLength(1);
    expect(logs.contextOf("evaluated pull request")).toMatchObject({
      reason: "no recorded head",
    });
  });

  it("ignores comments by anyone but the bot", async () => {
    const target = pullRequest();
    const github = withLabeled(target);
    github.setComments(target, [
      comment({ author: "monalisa", body: reviewMarker("sha-1") }),
    ]);

    const result = await fetch(github)();

    expect(result.pullRequests).toHaveLength(1);
  });

  it("carries the comments alongside the pull request", async () => {
    const target = pullRequest();
    const github = withLabeled(target);
    const comments = [comment({ author: "monalisa", body: "hi" })];
    github.setComments(target, comments);

    const result = await fetch(github)();

    expect(result.pullRequests[0]?.comments).toEqual(comments);
  });

  it("ensures the label on every repository it scans", async () => {
    const github = withLabeled(pullRequest());
    github.pullRequests["monalisa/other"] = [];

    await fetch(github)();

    expect(github.ensureLabelCalls).toEqual([
      [REPOSITORY, "angel", "f709c2"],
      ["monalisa/other", "angel", "f709c2"],
    ]);
  });

  it("ensures the label before listing", async () => {
    const github = withLabeled(pullRequest());

    await fetch(github)();

    expect(github.callLog).toEqual([
      ["ensureLabel", REPOSITORY],
      ["listOpenPullRequests", REPOSITORY],
    ]);
  });

  it("records a repository-level failure and keeps scanning", async () => {
    const github = withLabeled(pullRequest());
    github.pullRequests["monalisa/broken"] = [];
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
        stage: "fetch_pull_requests",
        errorType: "Error",
        error: "403",
      },
    ]);
    expect(result.pullRequests).toHaveLength(1);
  });

  it("records an item-level failure and keeps scanning the repository", async () => {
    const first = pullRequest({ number: 1 });
    const second = pullRequest({ number: 2, headSha: "sha-2" });
    const github = withLabeled(first, second);
    github.listComments = async (target) => {
      if (target.number === 1) {
        throw new Error("500");
      }
      return [];
    };

    const result = await fetch(github)();

    expect(result.failures).toEqual([
      {
        repository: REPOSITORY,
        number: 1,
        stage: "fetch_pull_requests",
        errorType: "Error",
        error: "500",
      },
    ]);
    expect(result.pullRequests.map((each) => each.pullRequest.number)).toEqual([2]);
  });

  it("logs how much it scanned and how much is due", async () => {
    const github = withLabeled(pullRequest(), pullRequest({ number: 2 }));

    await fetch(github)();

    expect(logs.contextOf("pull requests fetched")).toEqual({
      repositories_scanned: 1,
      items_scanned: 2,
      items_due_for_review: 2,
    });
  });
});

describe("reviewPullRequests", () => {
  const logs = useLogCapture();

  function context(overrides: Partial<PullRequest> = {}): PullRequestContext {
    return { pullRequest: pullRequest(overrides), comments: [] };
  }

  it("calls the model once per lens", async () => {
    const client = new FakeLlmClient();
    const github = new FakeGitHubClient();

    await reviewPullRequests(github, client)({ pullRequests: [context()] });

    expect(client.calls).toHaveLength(REVIEW_LENSES.length);
  });

  it("sends each lens its own system prompt", async () => {
    const client = new FakeLlmClient();

    await reviewPullRequests(
      new FakeGitHubClient(),
      client,
    )({
      pullRequests: [context()],
    });

    const prompts = client.calls.map((call) => {
      const system = call[0];
      return system instanceof SystemMessage ? system.content : undefined;
    });
    expect(new Set(prompts).size).toBe(REVIEW_LENSES.length);
  });

  it("puts the title, body, comments and diff in the human message", async () => {
    const client = new FakeLlmClient();
    const github = new FakeGitHubClient();
    const target = pullRequest();
    github.setDiff(target, "the diff");

    await reviewPullRequests(
      github,
      client,
    )({
      pullRequests: [
        { pullRequest: target, comments: [comment({ author: "octocat", body: "hi" })] },
      ],
    });

    const [, human] = client.lastCall;
    expect(human?.content).toContain("a pr");
    expect(human?.content).toContain("a body");
    expect(human?.content).toContain("@octocat: hi");
    expect(human?.content).toContain("the diff");
  });

  it("ends the body with the head sha marker", async () => {
    const client = new FakeLlmClient();

    const result = await reviewPullRequests(
      new FakeGitHubClient(),
      client,
    )({
      pullRequests: [context({ headSha: "sha-9" })],
    });

    expect(result.reviews[0]?.body.endsWith(reviewMarker("sha-9"))).toBe(true);
  });

  it("renders a section per lens", async () => {
    const client = new FakeLlmClient();

    const result = await reviewPullRequests(
      new FakeGitHubClient(),
      client,
    )({
      pullRequests: [context()],
    });

    const body = result.reviews[0]?.body ?? "";
    expect(body).toContain("### Security");
    expect(body).toContain("### Quality");
    expect(body).toContain("### Performance");
  });

  it("fails the whole pull request when one lens fails", async () => {
    const client = new FakeLlmClient();
    client.failStructuredCall = 2;

    const result = await reviewPullRequests(
      new FakeGitHubClient(),
      client,
    )({
      pullRequests: [context()],
    });

    expect(result.reviews).toEqual([]);
    expect(result.failures).toEqual([
      {
        repository: REPOSITORY,
        number: 1,
        stage: "review_pull_requests",
        errorType: "Error",
        error: "llm exploded",
      },
    ]);
  });

  it("keeps reviewing after one pull request fails", async () => {
    const client = new FakeLlmClient();
    client.failStructuredCall = 1;

    const result = await reviewPullRequests(
      new FakeGitHubClient(),
      client,
    )({
      pullRequests: [context({ number: 1 }), context({ number: 2 })],
    });

    expect(result.reviews.map((each) => each.target.number)).toEqual([2]);
    expect(result.failures).toHaveLength(1);
  });

  it("logs one review-produced record per lens", async () => {
    const client = new FakeLlmClient();

    await reviewPullRequests(
      new FakeGitHubClient(),
      client,
    )({
      pullRequests: [context()],
    });

    expect(logs.withMessage("review produced").map((r) => r.context.lens)).toEqual([
      "security",
      "quality",
      "performance",
    ]);
  });

  it("logs the diff size and lens count before reviewing", async () => {
    const client = new FakeLlmClient();
    const github = new FakeGitHubClient();
    const target = pullRequest();
    github.setDiff(target, "12345");

    await reviewPullRequests(
      github,
      client,
    )({
      pullRequests: [{ pullRequest: target, comments: [] }],
    });

    expect(logs.contextOf("reviewing pull request")).toMatchObject({
      diff_size: 5,
      lens_count: 3,
    });
  });

  it("says (none) when a pull request has no comments", async () => {
    const client = new FakeLlmClient();

    await reviewPullRequests(
      new FakeGitHubClient(),
      client,
    )({
      pullRequests: [context()],
    });

    expect(contentsOf(client.lastCall).join("\n")).toContain("(none)");
  });
});

describe("renderMergedReview", () => {
  it("puts one bold summary line per lens above the sections", () => {
    const body = renderMergedReview([
      { lens: "security", output: { summary: "clean", findings: [] } },
      { lens: "quality", output: { summary: "tidy", findings: [] } },
    ]);

    expect(body.split("\n\n")[0]).toBe("**Security:** clean");
    expect(body).toContain("**Quality:** tidy");
    expect(body).toContain("### Security\n\nNo findings.");
  });
});
