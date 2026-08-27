import { describe, expect, it } from "vitest";
import {
  buildGithubClient,
  GITHUB_BASE_URL,
  HttpGitHubClient,
  MissingGitHubCredentialsError,
  type PullRequest,
  type TokenProvider,
} from "../../../src/clients/github.js";
import { HttpClient, HttpStatusError } from "../../../src/clients/http.js";
import { resetEnvCache } from "../../../src/env.js";
import { FakeFetch } from "../../helpers/fetch.js";
import { loadFixture } from "../../helpers/fixtures.js";
import { rsaKeyPair } from "../../helpers/keys.js";
import { useTemporaryDirectory } from "../../helpers/tmp.js";

const REPOSITORY = "monalisa/hello-world";

class FakeTokenProvider implements TokenProvider {
  constructor(private readonly repositories: string[] = []) {}

  async tokenFor(repository: string): Promise<string> {
    return `token-for-${repository}`;
  }

  async listRepositories(): Promise<string[]> {
    return this.repositories;
  }
}

function build(fake: FakeFetch, provider = new FakeTokenProvider()) {
  return new HttpGitHubClient(
    new HttpClient(GITHUB_BASE_URL, {}, fake.fetch),
    provider,
  );
}

const PULL_REQUEST: PullRequest = {
  repository: REPOSITORY,
  number: 41,
  title: "a pr",
  body: "",
  headSha: "sha",
};

describe("listRepositories", () => {
  it("comes from the token provider", async () => {
    const client = build(new FakeFetch(), new FakeTokenProvider(["org/a", "org/b"]));

    await expect(client.listRepositories()).resolves.toEqual(["org/a", "org/b"]);
  });
});

describe("listOpenPullRequests", () => {
  it("maps number, title, body and head sha", async () => {
    const fake = new FakeFetch().onJson(
      "GET",
      `/repos/${REPOSITORY}/pulls`,
      loadFixture("github/pulls_page1.json"),
    );

    const pullRequests = await build(fake).listOpenPullRequests(REPOSITORY, "angel");

    expect(pullRequests).toContainEqual({
      repository: REPOSITORY,
      number: 41,
      title: "Paginate every GitHub list call",
      body: 'Follows the `Link: rel="next"` header on every list endpoint.',
      headSha: "9f1b0c4bd2a54a1e6e2b7dbb1a0dd4b13ec2f0a1",
    });
    const request = fake.lastCall;
    expect(request.url.searchParams.get("state")).toBe("open");
    expect(request.url.searchParams.get("per_page")).toBe("100");
    expect(request.headers.get("authorization")).toBe(`Bearer token-for-${REPOSITORY}`);
  });

  it("drops pull requests without the label", async () => {
    const fake = new FakeFetch().onJson(
      "GET",
      `/repos/${REPOSITORY}/pulls`,
      loadFixture("github/pulls_page1.json"),
    );

    const pullRequests = await build(fake).listOpenPullRequests(REPOSITORY, "angel");

    expect(pullRequests.map((each) => each.number)).toEqual([41]);
  });

  it("follows Link header pagination", async () => {
    const fake = new FakeFetch().on("GET", `/repos/${REPOSITORY}/pulls`, (request) =>
      request.url.searchParams.get("page") === "2"
        ? Response.json(loadFixture("github/pulls_page2.json"))
        : Response.json(loadFixture("github/pulls_page1.json"), {
            headers: {
              link:
                `<${GITHUB_BASE_URL}/repos/${REPOSITORY}/pulls` +
                '?state=open&per_page=100&page=2>; rel="next"',
            },
          }),
    );

    const pullRequests = await build(fake).listOpenPullRequests(REPOSITORY, "angel");

    expect(new Set(pullRequests.map((each) => each.number))).toEqual(new Set([41, 12]));
  });

  it("raises on a non-2xx response", async () => {
    const fake = new FakeFetch().on(
      "GET",
      `/repos/${REPOSITORY}/pulls`,
      new Response("boom", { status: 500 }),
    );

    await expect(build(fake).listOpenPullRequests(REPOSITORY, "angel")).rejects.toThrow(
      HttpStatusError,
    );
  });
});

describe("listOpenIssues", () => {
  it("excludes pull requests and maps updated_at", async () => {
    const fake = new FakeFetch().onJson(
      "GET",
      `/repos/${REPOSITORY}/issues`,
      loadFixture("github/issues.json"),
    );

    const issues = await build(fake).listOpenIssues(REPOSITORY, "angel");

    expect(issues).toEqual([
      {
        repository: REPOSITORY,
        number: 38,
        title: "Add a LICENSE",
        body: "",
        updatedAt: "2026-08-13T15:22:47Z",
      },
    ]);
    const request = fake.lastCall;
    expect(request.url.searchParams.get("state")).toBe("open");
    expect(request.url.searchParams.get("per_page")).toBe("100");
    expect(request.url.searchParams.get("labels")).toBe("angel");
  });

  it("follows Link header pagination", async () => {
    const fake = new FakeFetch().on("GET", `/repos/${REPOSITORY}/issues`, (request) =>
      request.url.searchParams.get("page") === "2"
        ? Response.json(loadFixture("github/issues_page2.json"))
        : Response.json(loadFixture("github/issues_page1.json"), {
            headers: {
              link:
                `<${GITHUB_BASE_URL}/repos/${REPOSITORY}/issues` +
                '?state=open&per_page=100&labels=angel&page=2>; rel="next"',
            },
          }),
    );

    const issues = await build(fake).listOpenIssues(REPOSITORY, "angel");

    expect(issues.map((each) => each.number)).toEqual([38]);
  });
});

describe("listComments", () => {
  it("maps login, body and created_at", async () => {
    const fake = new FakeFetch().onJson(
      "GET",
      `/repos/${REPOSITORY}/issues/41/comments`,
      loadFixture("github/comments_page1.json"),
    );

    const comments = await build(fake).listComments(PULL_REQUEST);

    expect(comments).toEqual([
      {
        author: "monalisa",
        body: "Ready for a look.",
        createdAt: "2026-08-14T11:04:02Z",
      },
      { author: "octocat", body: "", createdAt: "2026-08-14T12:20:35Z" },
    ]);
    expect(fake.lastCall.url.searchParams.get("per_page")).toBe("100");
  });

  it("follows Link header pagination", async () => {
    const fake = new FakeFetch().on(
      "GET",
      `/repos/${REPOSITORY}/issues/41/comments`,
      (request) =>
        request.url.searchParams.get("page") === "2"
          ? Response.json(loadFixture("github/comments_page2.json"))
          : Response.json(loadFixture("github/comments_page1.json"), {
              headers: {
                link:
                  `<${GITHUB_BASE_URL}/repos/${REPOSITORY}/issues/41/comments` +
                  '?per_page=100&page=2>; rel="next"',
              },
            }),
    );

    const comments = await build(fake).listComments(PULL_REQUEST);

    expect(new Set(comments.map((each) => each.author))).toEqual(
      new Set(["monalisa", "octocat", "kandy-angel[bot]"]),
    );
  });
});

describe("fetchDiff", () => {
  it("asks for the diff media type and returns the body verbatim", async () => {
    const diff = loadFixture<string>("github/pull_request.diff");
    const fake = new FakeFetch().on(
      "GET",
      `/repos/${REPOSITORY}/pulls/41`,
      new Response(diff, { status: 200 }),
    );

    await expect(build(fake).fetchDiff(PULL_REQUEST)).resolves.toBe(diff);
    expect(fake.lastCall.headers.get("accept")).toBe("application/vnd.github.diff");
    expect(fake.lastCall.headers.get("authorization")).toBe(
      `Bearer token-for-${REPOSITORY}`,
    );
  });
});

describe("postComment", () => {
  it("sends the body to the issue comments endpoint", async () => {
    const fake = new FakeFetch().onJson(
      "POST",
      `/repos/${REPOSITORY}/issues/41/comments`,
      {},
      { status: 201 },
    );

    await build(fake).postComment(PULL_REQUEST, "great work");

    expect(JSON.parse(fake.lastCall.body ?? "")).toEqual({ body: "great work" });
    expect(fake.lastCall.headers.get("authorization")).toBe(
      `Bearer token-for-${REPOSITORY}`,
    );
  });
});

describe("ensureLabel", () => {
  it("does not create the label when it already exists", async () => {
    const fake = new FakeFetch().onJson(
      "GET",
      `/repos/${REPOSITORY}/labels/angel`,
      loadFixture("github/label.json"),
    );

    await build(fake).ensureLabel(REPOSITORY, "angel", "f709c2");

    expect(fake.callsTo("GET", `/repos/${REPOSITORY}/labels/angel`)).toHaveLength(1);
    expect(fake.callsTo("POST", `/repos/${REPOSITORY}/labels`)).toHaveLength(0);
  });

  it("creates the label when it is missing", async () => {
    const fake = new FakeFetch()
      .onJson(
        "GET",
        `/repos/${REPOSITORY}/labels/angel`,
        loadFixture("github/label_not_found.json"),
        { status: 404 },
      )
      .onJson("POST", `/repos/${REPOSITORY}/labels`, loadFixture("github/label.json"), {
        status: 201,
      });

    await build(fake).ensureLabel(REPOSITORY, "angel", "f709c2");

    expect(JSON.parse(fake.lastCall.body ?? "")).toEqual({
      name: "angel",
      color: "f709c2",
    });
  });

  it("raises when the label lookup fails for another reason", async () => {
    const fake = new FakeFetch().on(
      "GET",
      `/repos/${REPOSITORY}/labels/angel`,
      new Response("nope", { status: 403 }),
    );

    await expect(
      build(fake).ensureLabel(REPOSITORY, "angel", "f709c2"),
    ).rejects.toThrow(HttpStatusError);
  });
});

describe("buildGithubClient", () => {
  const temporary = useTemporaryDirectory();

  function clearCredentials() {
    resetEnvCache();
    delete process.env.ANGEL_GITHUB_APP_ID;
    delete process.env.ANGEL_GITHUB_PRIVATE_KEY_PATH;
  }

  it("raises when the app id is missing", () => {
    clearCredentials();
    process.env.ANGEL_GITHUB_PRIVATE_KEY_PATH = `${temporary.path}/key.pem`;

    expect(() => buildGithubClient()).toThrow(MissingGitHubCredentialsError);
    expect(() => buildGithubClient()).toThrow(/ANGEL_GITHUB_APP_ID/);
  });

  it("raises when the private key path is missing", () => {
    clearCredentials();
    process.env.ANGEL_GITHUB_APP_ID = "app-1";

    expect(() => buildGithubClient()).toThrow(/ANGEL_GITHUB_PRIVATE_KEY_PATH/);
  });

  it("names both variables when neither is set", () => {
    clearCredentials();

    expect(() => buildGithubClient()).toThrow(
      /ANGEL_GITHUB_APP_ID.*ANGEL_GITHUB_PRIVATE_KEY_PATH/s,
    );
  });

  it("sends the API version header and no ambient authorization", async () => {
    const { writeFileSync } = await import("node:fs");
    clearCredentials();
    const keyPath = `${temporary.path}/key.pem`;
    writeFileSync(keyPath, rsaKeyPair().privateKey);
    process.env.ANGEL_GITHUB_APP_ID = "app-1";
    process.env.ANGEL_GITHUB_PRIVATE_KEY_PATH = keyPath;

    const client = buildGithubClient();

    expect(client).toBeInstanceOf(HttpGitHubClient);
    expect(client.httpClient.defaultHeaders).toEqual({
      "x-github-api-version": "2022-11-28",
    });
  });
});
