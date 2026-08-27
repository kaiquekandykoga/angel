import type {
  Comment,
  GitHubClient,
  Issue,
  PullRequest,
  ReviewTarget,
} from "../../apps/server/clients/github.js";

function key(target: ReviewTarget): string {
  return `${target.repository}#${target.number}`;
}

export class FakeGitHubClient implements GitHubClient {
  pullRequests: Record<string, PullRequest[]> = {};
  issues: Record<string, Issue[]> = {};
  diffs = new Map<string, string>();
  comments = new Map<string, Comment[]>();
  postedComments: [ReviewTarget, string][] = [];
  labels = new Map<string, Set<string>>();
  ensureLabelCalls: [string, string, string][] = [];
  callLog: [string, string][] = [];

  label(target: ReviewTarget, label: string): void {
    const labels = this.labels.get(key(target)) ?? new Set<string>();
    labels.add(label);
    this.labels.set(key(target), labels);
  }

  setDiff(pullRequest: PullRequest, diff: string): void {
    this.diffs.set(key(pullRequest), diff);
  }

  setComments(target: ReviewTarget, comments: Comment[]): void {
    this.comments.set(key(target), comments);
  }

  async listRepositories(): Promise<string[]> {
    return [
      ...new Set([...Object.keys(this.pullRequests), ...Object.keys(this.issues)]),
    ].sort();
  }

  async ensureLabel(repository: string, label: string, color: string): Promise<void> {
    this.ensureLabelCalls.push([repository, label, color]);
    this.callLog.push(["ensureLabel", repository]);
  }

  async listOpenPullRequests(
    repository: string,
    label: string,
  ): Promise<PullRequest[]> {
    this.callLog.push(["listOpenPullRequests", repository]);
    return (this.pullRequests[repository] ?? []).filter((pullRequest) =>
      this.labels.get(key(pullRequest))?.has(label),
    );
  }

  async fetchDiff(pullRequest: PullRequest): Promise<string> {
    return this.diffs.get(key(pullRequest)) ?? "";
  }

  async listOpenIssues(repository: string, label: string): Promise<Issue[]> {
    this.callLog.push(["listOpenIssues", repository]);
    return (this.issues[repository] ?? []).filter((issue) =>
      this.labels.get(key(issue))?.has(label),
    );
  }

  async listComments(target: ReviewTarget): Promise<Comment[]> {
    return this.comments.get(key(target)) ?? [];
  }

  async postComment(target: ReviewTarget, body: string): Promise<void> {
    this.postedComments.push([target, body]);
  }
}
