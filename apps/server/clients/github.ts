import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import jwt from "jsonwebtoken";
import { loadEnvVar } from "../../../packages/shared/env.js";
import { getLogger } from "../../../packages/shared/logs.js";
import { type FetchLike, getAll, HttpClient } from "./http.js";

const log = getLogger("angel.clients.github");

export const GITHUB_BASE_URL = "https://api.github.com";
export const GITHUB_API_VERSION = "2022-11-28";

const PER_PAGE = 100;
const JWT_LEEWAY_SECONDS = 60;
const JWT_LIFETIME_SECONDS = 540;

export interface PullRequest {
  readonly repository: string;
  readonly number: number;
  readonly title: string;
  readonly body: string;
  readonly headSha: string;
}

export interface Issue {
  readonly repository: string;
  readonly number: number;
  readonly title: string;
  readonly body: string;
  readonly updatedAt: string;
}

export interface Comment {
  readonly author: string;
  readonly body: string;
  readonly createdAt: string;
}

export type ReviewTarget = PullRequest | Issue;

export interface GitHubClient {
  listRepositories(): Promise<string[]>;
  ensureLabel(repository: string, label: string, color: string): Promise<void>;
  listOpenPullRequests(repository: string, label: string): Promise<PullRequest[]>;
  fetchDiff(pullRequest: PullRequest): Promise<string>;
  listOpenIssues(repository: string, label: string): Promise<Issue[]>;
  listComments(target: ReviewTarget): Promise<Comment[]>;
  postComment(target: ReviewTarget, body: string): Promise<void>;
}

export interface TokenProvider {
  tokenFor(repository: string): Promise<string>;
  listRepositories(): Promise<string[]>;
}

export class MissingGitHubCredentialsError extends Error {
  override readonly name = "MissingGitHubCredentialsError";
}

interface ApiLabelRef {
  readonly name: string;
}

interface ApiPullRequest {
  readonly number: number;
  readonly title: string;
  readonly body: string | null;
  readonly head: { readonly sha: string };
  readonly labels: readonly ApiLabelRef[];
}

interface ApiIssue {
  readonly number: number;
  readonly title: string;
  readonly body: string | null;
  readonly updated_at: string;
  readonly pull_request?: unknown;
}

interface ApiComment {
  readonly user: { readonly login: string };
  readonly body: string | null;
  readonly created_at: string;
}

interface ApiInstallation {
  readonly id: number;
}

interface ApiRepository {
  readonly full_name: string;
}

interface ApiAccessToken {
  readonly token: string;
}

export class InstallationTokenProvider implements TokenProvider {
  private readonly tokens = new Map<string, string>();

  constructor(
    private readonly httpClient: HttpClient,
    private readonly appId: string,
    private readonly privateKey: string,
    private readonly now: () => number = () => Math.floor(Date.now() / 1000),
  ) {}

  private jwtHeader(): Record<string, string> {
    const now = this.now();
    const token = jwt.sign(
      {
        iat: now - JWT_LEEWAY_SECONDS,
        exp: now + JWT_LIFETIME_SECONDS,
        iss: this.appId,
      },
      this.privateKey,
      { algorithm: "RS256" },
    );
    return { authorization: `Bearer ${token}` };
  }

  private async createToken(
    installationId: number,
    headers: Record<string, string>,
  ): Promise<string> {
    const response = (
      await this.httpClient.post(`/app/installations/${installationId}/access_tokens`, {
        headers,
      })
    ).ensureOk();
    return (await response.json<ApiAccessToken>()).token;
  }

  async tokenFor(repository: string): Promise<string> {
    const cached = this.tokens.get(repository);
    if (cached !== undefined) {
      return cached;
    }
    const headers = this.jwtHeader();
    const response = (
      await this.httpClient.get(`/repos/${repository}/installation`, { headers })
    ).ensureOk();
    const { id } = await response.json<ApiInstallation>();

    const token = await this.createToken(id, headers);
    this.tokens.set(repository, token);
    return token;
  }

  async listRepositories(): Promise<string[]> {
    const headers = this.jwtHeader();
    const installations = await getAll<ApiInstallation>(
      this.httpClient,
      "/app/installations",
      { params: { per_page: PER_PAGE }, headers },
    );

    const repositories: string[] = [];
    for (const installation of installations) {
      const token = await this.createToken(installation.id, headers);
      const owned = await getAll<ApiRepository>(
        this.httpClient,
        "/installation/repositories",
        {
          params: { per_page: PER_PAGE },
          headers: { authorization: `Bearer ${token}` },
          key: "repositories",
        },
      );
      for (const repository of owned) {
        this.tokens.set(repository.full_name, token);
        repositories.push(repository.full_name);
      }
    }
    return repositories;
  }
}

export class HttpGitHubClient implements GitHubClient {
  constructor(
    readonly httpClient: HttpClient,
    private readonly tokenProvider: TokenProvider,
  ) {}

  private async authHeader(repository: string): Promise<Record<string, string>> {
    return { authorization: `Bearer ${await this.tokenProvider.tokenFor(repository)}` };
  }

  listRepositories(): Promise<string[]> {
    return this.tokenProvider.listRepositories();
  }

  async ensureLabel(repository: string, label: string, color: string): Promise<void> {
    const response = await this.httpClient.get(`/repos/${repository}/labels/${label}`, {
      headers: await this.authHeader(repository),
    });
    if (response.status === 404) {
      (
        await this.httpClient.post(`/repos/${repository}/labels`, {
          json: { name: label, color },
          headers: await this.authHeader(repository),
        })
      ).ensureOk();
      return;
    }
    response.ensureOk();
  }

  async listOpenPullRequests(
    repository: string,
    label: string,
  ): Promise<PullRequest[]> {
    const items = await getAll<ApiPullRequest>(
      this.httpClient,
      `/repos/${repository}/pulls`,
      {
        params: { state: "open", per_page: PER_PAGE },
        headers: await this.authHeader(repository),
      },
    );
    return items
      .filter((item) => item.labels.some((each) => each.name === label))
      .map((item) => ({
        repository,
        number: item.number,
        title: item.title,
        body: item.body ?? "",
        headSha: item.head.sha,
      }));
  }

  async fetchDiff(pullRequest: PullRequest): Promise<string> {
    const response = (
      await this.httpClient.get(
        `/repos/${pullRequest.repository}/pulls/${pullRequest.number}`,
        {
          headers: {
            accept: "application/vnd.github.diff",
            ...(await this.authHeader(pullRequest.repository)),
          },
        },
      )
    ).ensureOk();
    return response.text();
  }

  async listOpenIssues(repository: string, label: string): Promise<Issue[]> {
    const items = await getAll<ApiIssue>(
      this.httpClient,
      `/repos/${repository}/issues`,
      {
        params: { state: "open", per_page: PER_PAGE, labels: label },
        headers: await this.authHeader(repository),
      },
    );
    return items
      .filter((item) => item.pull_request === undefined)
      .map((item) => ({
        repository,
        number: item.number,
        title: item.title,
        body: item.body ?? "",
        updatedAt: item.updated_at,
      }));
  }

  async listComments(target: ReviewTarget): Promise<Comment[]> {
    const items = await getAll<ApiComment>(
      this.httpClient,
      `/repos/${target.repository}/issues/${target.number}/comments`,
      {
        params: { per_page: PER_PAGE },
        headers: await this.authHeader(target.repository),
      },
    );
    return items.map((item) => ({
      author: item.user.login,
      body: item.body ?? "",
      createdAt: item.created_at,
    }));
  }

  async postComment(target: ReviewTarget, body: string): Promise<void> {
    (
      await this.httpClient.post(
        `/repos/${target.repository}/issues/${target.number}/comments`,
        { json: { body }, headers: await this.authHeader(target.repository) },
      )
    ).ensureOk();
  }
}

export class DryRunGitHubClient implements GitHubClient {
  constructor(private readonly inner: GitHubClient) {}

  listRepositories(): Promise<string[]> {
    return this.inner.listRepositories();
  }

  async ensureLabel(repository: string, label: string, _color: string): Promise<void> {
    log.info("dry run: skipping ensure_label", {
      dry_run: true,
      repository,
      label,
    });
  }

  listOpenPullRequests(repository: string, label: string): Promise<PullRequest[]> {
    return this.inner.listOpenPullRequests(repository, label);
  }

  fetchDiff(pullRequest: PullRequest): Promise<string> {
    return this.inner.fetchDiff(pullRequest);
  }

  listOpenIssues(repository: string, label: string): Promise<Issue[]> {
    return this.inner.listOpenIssues(repository, label);
  }

  listComments(target: ReviewTarget): Promise<Comment[]> {
    return this.inner.listComments(target);
  }

  async postComment(target: ReviewTarget, body: string): Promise<void> {
    log.info("dry run: skipping post_comment", {
      dry_run: true,
      repository: target.repository,
      number: target.number,
      body_length: body.length,
    });
  }
}

function expandUser(path: string): string {
  return path.startsWith("~/") ? join(homedir(), path.slice(2)) : path;
}

export function buildGithubClient(fetchImpl?: FetchLike): HttpGitHubClient {
  const appId = loadEnvVar("ANGEL_GITHUB_APP_ID");
  const privateKeyPath = loadEnvVar("ANGEL_GITHUB_PRIVATE_KEY_PATH");
  if (!appId || !privateKeyPath) {
    const missing = (
      [
        ["ANGEL_GITHUB_APP_ID", appId],
        ["ANGEL_GITHUB_PRIVATE_KEY_PATH", privateKeyPath],
      ] as const
    )
      .filter(([, value]) => !value)
      .map(([name]) => `${name} environment variable is not set.`);
    throw new MissingGitHubCredentialsError(missing.join(" "));
  }

  const privateKey = readFileSync(expandUser(privateKeyPath), "utf8");
  const httpClient = new HttpClient(
    GITHUB_BASE_URL,
    { "x-github-api-version": GITHUB_API_VERSION },
    fetchImpl,
  );
  return new HttpGitHubClient(
    httpClient,
    new InstallationTokenProvider(httpClient, appId, privateKey),
  );
}
