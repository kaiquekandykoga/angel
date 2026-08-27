import jwt from "jsonwebtoken";
import { describe, expect, it } from "vitest";
import {
  GITHUB_BASE_URL,
  InstallationTokenProvider,
} from "../../../../apps/server/clients/github.js";
import { HttpClient } from "../../../../apps/server/clients/http.js";
import { FakeFetch } from "../../../helpers/fetch.js";
import { loadFixture } from "../../../helpers/fixtures.js";
import { rsaKeyPair } from "../../../helpers/keys.js";

const RECORDED_TOKEN = "ghs_REDACTEDINSTALLATIONTOKEN0000000000";

function build(fake: FakeFetch, now?: () => number) {
  return new InstallationTokenProvider(
    new HttpClient(GITHUB_BASE_URL, {}, fake.fetch),
    "app-1",
    rsaKeyPair().privateKey,
    now ?? (() => 1_800_000_000),
  );
}

describe("tokenFor", () => {
  it("exchanges the app JWT for an installation access token", async () => {
    const fake = new FakeFetch()
      .onJson("GET", "/repos/monalisa/hello-world/installation", { id: 123 })
      .onJson(
        "POST",
        "/app/installations/123/access_tokens",
        { token: "installation-token" },
        { status: 201 },
      );

    const token = await build(fake).tokenFor("monalisa/hello-world");

    expect(token).toBe("installation-token");
    expect(fake.calls.map((call) => call.url.pathname)).toEqual([
      "/repos/monalisa/hello-world/installation",
      "/app/installations/123/access_tokens",
    ]);
  });

  it("signs a short-lived RS256 JWT issued by the app", async () => {
    const fake = new FakeFetch()
      .onJson("GET", "/repos/monalisa/hello-world/installation", { id: 123 })
      .onJson(
        "POST",
        "/app/installations/123/access_tokens",
        { token: "t" },
        {
          status: 201,
        },
      );

    await build(fake).tokenFor("monalisa/hello-world");

    for (const call of fake.calls) {
      const header = call.headers.get("authorization") ?? "";
      expect(header.startsWith("Bearer ")).toBe(true);
      const claims = jwt.verify(
        header.slice("Bearer ".length),
        rsaKeyPair().publicKey,
        {
          algorithms: ["RS256"],
        },
      ) as jwt.JwtPayload;
      expect(claims.iss).toBe("app-1");
      expect((claims.exp ?? 0) - (claims.iat ?? 0)).toBeLessThanOrEqual(600);
    }
  });

  it("caches the token per repository", async () => {
    const fake = new FakeFetch()
      .onJson(
        "GET",
        "/repos/monalisa/hello-world/installation",
        loadFixture<{ id: number }[]>("github/installations.json")[0],
      )
      .onJson(
        "POST",
        "/app/installations/12345678/access_tokens",
        loadFixture("github/access_token.json"),
        { status: 201 },
      );
    const provider = build(fake);

    const first = await provider.tokenFor("monalisa/hello-world");
    const callsAfterFirst = fake.calls.length;
    const second = await provider.tokenFor("monalisa/hello-world");

    expect(first).toBe(RECORDED_TOKEN);
    expect(second).toBe(RECORDED_TOKEN);
    expect(fake.calls).toHaveLength(callsAfterFirst);
  });
});

describe("listRepositories", () => {
  it("spans every installation, in installation order", async () => {
    const repositoriesByToken: Record<string, string[]> = {
      "token-1": ["monalisa/hello-world", "monalisa/a"],
      "token-2": ["someone-else/b"],
    };
    const fake = new FakeFetch()
      .onJson("GET", "/app/installations", [{ id: 1 }, { id: 2 }])
      .onJson(
        "POST",
        "/app/installations/1/access_tokens",
        { token: "token-1" },
        {
          status: 201,
        },
      )
      .onJson(
        "POST",
        "/app/installations/2/access_tokens",
        { token: "token-2" },
        {
          status: 201,
        },
      )
      .on("GET", "/installation/repositories", (request) => {
        const token = (request.headers.get("authorization") ?? "").slice(
          "Bearer ".length,
        );
        return Response.json({
          repositories: (repositoriesByToken[token] ?? []).map((fullName) => ({
            full_name: fullName,
          })),
        });
      });

    await expect(build(fake).listRepositories()).resolves.toEqual([
      "monalisa/hello-world",
      "monalisa/a",
      "someone-else/b",
    ]);
  });

  it("caches the token of every repository it listed", async () => {
    const fake = new FakeFetch()
      .onJson("GET", "/app/installations", loadFixture("github/installations.json"))
      .onJson(
        "POST",
        "/app/installations/12345678/access_tokens",
        loadFixture("github/access_token.json"),
        { status: 201 },
      )
      .onJson(
        "GET",
        "/installation/repositories",
        loadFixture("github/installation_repositories_page1.json"),
      );
    const provider = build(fake);

    await provider.listRepositories();
    const callsAfterListing = fake.calls.length;

    await expect(provider.tokenFor("monalisa/hello-world")).resolves.toBe(
      RECORDED_TOKEN,
    );
    expect(fake.calls).toHaveLength(callsAfterListing);
  });

  it("follows Link header pagination over the repositories of one installation", async () => {
    const fake = new FakeFetch()
      .onJson("GET", "/app/installations", loadFixture("github/installations.json"))
      .onJson(
        "POST",
        "/app/installations/12345678/access_tokens",
        loadFixture("github/access_token.json"),
        { status: 201 },
      )
      .on("GET", "/installation/repositories", (request) =>
        request.url.searchParams.get("page") === "2"
          ? Response.json(loadFixture("github/installation_repositories_page2.json"))
          : Response.json(loadFixture("github/installation_repositories_page1.json"), {
              headers: {
                link:
                  `<${GITHUB_BASE_URL}/installation/repositories` +
                  '?per_page=100&page=2>; rel="next"',
              },
            }),
      );

    await expect(new Set(await build(fake).listRepositories())).toEqual(
      new Set(["monalisa/hello-world", "monalisa/octo-repo"]),
    );
  });

  it("follows Link header pagination over the installations themselves", async () => {
    const repositoryByInstallation: Record<string, string> = {
      "token-for-12345678": "monalisa/hello-world",
      "token-for-12345679": "monalisa/octo-repo",
    };
    const fake = new FakeFetch()
      .on("GET", "/app/installations", (request) =>
        request.url.searchParams.get("page") === "2"
          ? Response.json(loadFixture("github/installations_page2.json"))
          : Response.json(loadFixture("github/installations_page1.json"), {
              headers: {
                link:
                  `<${GITHUB_BASE_URL}/app/installations` +
                  '?per_page=100&page=2>; rel="next"',
              },
            }),
      )
      .onJson(
        "POST",
        "/app/installations/12345678/access_tokens",
        { token: "token-for-12345678" },
        { status: 201 },
      )
      .onJson(
        "POST",
        "/app/installations/12345679/access_tokens",
        { token: "token-for-12345679" },
        { status: 201 },
      )
      .on("GET", "/installation/repositories", (request) => {
        const token = (request.headers.get("authorization") ?? "").slice(
          "Bearer ".length,
        );
        const fullName = repositoryByInstallation[token];
        return Response.json({
          repositories: fullName === undefined ? [] : [{ full_name: fullName }],
        });
      });

    await expect(new Set(await build(fake).listRepositories())).toEqual(
      new Set(["monalisa/hello-world", "monalisa/octo-repo"]),
    );
  });
});
