import { describe, expect, it } from "vitest";
import {
  type Comment,
  dryRunClient,
  type GitHubClient,
  type Issue,
  type PullRequest,
  type ReviewTarget,
} from "../../../../../apps/server/external/github/client.js";
import { useLogCapture } from "../../../../helpers/logs.js";

const PULL_REQUEST: PullRequest = {
  repository: "org/repo",
  number: 1,
  title: "title",
  body: "body",
  headSha: "sha",
};

const ISSUE: Issue = {
  repository: "org/repo",
  number: 2,
  title: "title",
  body: "body",
  updatedAt: "2024-01-01T00:00:00Z",
};

class SpyGitHubClient implements GitHubClient {
  readonly calls: [string, unknown[]][] = [];

  async listRepositories(): Promise<string[]> {
    this.calls.push(["listRepositories", []]);
    return ["org/repo"];
  }

  async ensureLabel(repository: string, label: string, color: string): Promise<void> {
    this.calls.push(["ensureLabel", [repository, label, color]]);
  }

  async listOpenPullRequests(
    repository: string,
    label: string,
  ): Promise<PullRequest[]> {
    this.calls.push(["listOpenPullRequests", [repository, label]]);
    return [PULL_REQUEST];
  }

  async fetchDiff(pullRequest: PullRequest): Promise<string> {
    this.calls.push(["fetchDiff", [pullRequest]]);
    return "diff";
  }

  async listOpenIssues(repository: string, label: string): Promise<Issue[]> {
    this.calls.push(["listOpenIssues", [repository, label]]);
    return [ISSUE];
  }

  async listComments(target: ReviewTarget): Promise<Comment[]> {
    this.calls.push(["listComments", [target]]);
    return [{ author: "author", body: "body", createdAt: "2024-01-01T00:00:00Z" }];
  }

  async postComment(target: ReviewTarget, body: string): Promise<void> {
    this.calls.push(["postComment", [target, body]]);
  }
}

describe("dryRunClient", () => {
  const logs = useLogCapture();

  it("forwards every read", async () => {
    const inner = new SpyGitHubClient();
    const client = dryRunClient(inner);

    await expect(client.listRepositories()).resolves.toEqual(["org/repo"]);
    await expect(client.listOpenPullRequests("org/repo", "review")).resolves.toEqual([
      PULL_REQUEST,
    ]);
    await expect(client.fetchDiff(PULL_REQUEST)).resolves.toBe("diff");
    await expect(client.listOpenIssues("org/repo", "bug")).resolves.toEqual([ISSUE]);
    await expect(client.listComments(ISSUE)).resolves.toHaveLength(1);

    expect(inner.calls.map(([name]) => name)).toEqual([
      "listRepositories",
      "listOpenPullRequests",
      "fetchDiff",
      "listOpenIssues",
      "listComments",
    ]);
  });

  it("skips ensureLabel and logs what it would have written", async () => {
    const inner = new SpyGitHubClient();

    await dryRunClient(inner).ensureLabel("org/repo", "bug", "ff0000");

    expect(inner.calls).toEqual([]);
    expect(logs.contextOf("dry run: skipping ensure_label")).toEqual({
      dry_run: true,
      repository: "org/repo",
      label: "bug",
    });
  });

  it("skips postComment and logs the body length", async () => {
    const inner = new SpyGitHubClient();

    await dryRunClient(inner).postComment(PULL_REQUEST, "hello world");

    expect(inner.calls).toEqual([]);
    expect(logs.contextOf("dry run: skipping post_comment")).toEqual({
      dry_run: true,
      repository: "org/repo",
      number: 1,
      body_length: 11,
    });
  });
});
