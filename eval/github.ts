import type {
  Comment,
  GitHubClient,
  Issue,
  PullRequest,
  ReviewTarget,
} from "../apps/server/index.js";

export interface StaticRepository {
  readonly repository: string;
  readonly pullRequests: readonly PullRequest[];
  readonly issues: readonly Issue[];
  readonly diffs: ReadonlyMap<number, string>;
  readonly comments: ReadonlyMap<number, readonly Comment[]>;
}

export class StaticGitHubClient implements GitHubClient {
  readonly posted: { target: ReviewTarget; body: string }[] = [];

  constructor(private readonly repository: StaticRepository) {}

  async listRepositories(): Promise<string[]> {
    return [this.repository.repository];
  }

  async ensureLabel(
    _repository: string,
    _label: string,
    _color: string,
  ): Promise<void> {}

  async listOpenPullRequests(
    _repository: string,
    _label: string,
  ): Promise<PullRequest[]> {
    return [...this.repository.pullRequests];
  }

  async fetchDiff(pullRequest: PullRequest): Promise<string> {
    return this.repository.diffs.get(pullRequest.number) ?? "";
  }

  async listOpenIssues(_repository: string, _label: string): Promise<Issue[]> {
    return [...this.repository.issues];
  }

  async listComments(target: ReviewTarget): Promise<Comment[]> {
    return [...(this.repository.comments.get(target.number) ?? [])];
  }

  async postComment(target: ReviewTarget, body: string): Promise<void> {
    this.posted.push({ target, body });
  }
}
