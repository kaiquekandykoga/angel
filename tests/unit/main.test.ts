import { afterEach, describe, expect, it, vi } from "vitest";
import { ExitError } from "../../src/cli.js";
import {
  type GitHubClient,
  type Issue,
  MissingGitHubCredentialsError,
  type PullRequest,
} from "../../src/clients/github.js";
import {
  InvalidMaxCompletionTokensError,
  type LlmClient,
  MissingApiKeyError,
  resetUsage,
} from "../../src/clients/llm.js";
import { resetEnvCache } from "../../src/env.js";
import { type MainDependencies, main, start } from "../../src/main.js";
import { stripAnsi } from "../helpers/ansi.js";
import { FakeGitHubClient } from "../helpers/github.js";
import { FakeLlmClient } from "../helpers/llm.js";
import { useLogCapture } from "../helpers/logs.js";
import { MemoryStream } from "../helpers/stream.js";
import { useTemporaryDirectory } from "../helpers/tmp.js";

const REPOSITORY = "monalisa/hello-world";

function pullRequest(number: number): PullRequest {
  return {
    repository: REPOSITORY,
    number,
    title: `pr ${number}`,
    body: `body ${number}`,
    headSha: `sha-${number}`,
  };
}

function issue(number: number): Issue {
  return {
    repository: REPOSITORY,
    number,
    title: `issue ${number}`,
    body: `body ${number}`,
    updatedAt: "2026-08-01T00:00:00Z",
  };
}

interface Harness {
  readonly stdout: MemoryStream;
  readonly stderr: MemoryStream;
  readonly client: FakeLlmClient;
  readonly github: FakeGitHubClient;
  readonly sessionsRun: number[];
  readonly dependencies: MainDependencies;
}

function harness(overrides: Partial<MainDependencies> = {}): Harness {
  const stdout = new MemoryStream();
  const stderr = new MemoryStream();
  const client = new FakeLlmClient();
  const github = new FakeGitHubClient();
  const sessionsRun: number[] = [];
  resetUsage();
  return {
    stdout,
    stderr,
    client,
    github,
    sessionsRun,
    dependencies: {
      buildLlmClient: (): LlmClient => client,
      buildGithubClient: (): GitHubClient => github,
      runRepl: async () => {
        sessionsRun.push(1);
      },
      configureLogging: () => "log/angel-20260807T000000Z.jsonl",
      stdout,
      stderr,
      ...overrides,
    },
  };
}

function labeledPullRequests(github: FakeGitHubClient, ...numbers: number[]): void {
  const pullRequests = numbers.map(pullRequest);
  github.pullRequests = { [REPOSITORY]: pullRequests };
  for (const each of pullRequests) {
    github.label(each, "angel");
    github.setDiff(each, `diff ${each.number}`);
  }
}

function labeledIssues(github: FakeGitHubClient, ...numbers: number[]): void {
  const issues = numbers.map(issue);
  github.issues = { [REPOSITORY]: issues };
  for (const each of issues) {
    github.label(each, "angel");
  }
}

async function expectExit(promise: Promise<unknown>): Promise<ExitError> {
  try {
    await promise;
  } catch (error) {
    if (error instanceof ExitError) {
      return error;
    }
    throw error;
  }
  throw new Error("expected an ExitError");
}

describe("main help and errors", () => {
  it("prints the top-level help and exits 0 with no arguments", async () => {
    const { stdout, dependencies } = harness();

    const error = await expectExit(main([], dependencies));

    expect(error.code).toBe(0);
    expect(stdout.text).toContain("usage: angel");
  });

  it("exits 1 on an unknown command without configuring logging", async () => {
    let configured = false;
    const { dependencies } = harness({
      configureLogging: () => {
        configured = true;
        return "log/x.jsonl";
      },
    });

    const error = await expectExit(main(["bogus"], dependencies));

    expect(error.code).toBe(1);
    expect(error.message).toContain("Unknown command: bogus.");
    expect(configured).toBe(false);
  });

  it("exits with the message when the API key is missing", async () => {
    const message = "ANGEL_NVIDIA_API_KEY environment variable is not set.";
    const { dependencies } = harness({
      buildLlmClient: () => {
        throw new MissingApiKeyError(message);
      },
    });

    await expect(expectExit(main(["chat"], dependencies))).resolves.toMatchObject({
      code: 1,
      message,
    });
  });

  it("exits with the message when the token ceiling is invalid", async () => {
    const { dependencies } = harness({
      buildLlmClient: () => {
        throw new InvalidMaxCompletionTokensError("bad ceiling");
      },
    });

    await expect(expectExit(main(["chat"], dependencies))).resolves.toMatchObject({
      message: "bad ceiling",
    });
  });

  it("exits with the message when GitHub credentials are missing", async () => {
    const { dependencies } = harness({
      buildGithubClient: () => {
        throw new MissingGitHubCredentialsError("no app id");
      },
    });

    await expect(expectExit(main(["pr_review"], dependencies))).resolves.toMatchObject({
      message: "no app id",
    });
  });

  it("lets an unexpected error through rather than swallowing it", async () => {
    const { dependencies } = harness({
      buildLlmClient: () => {
        throw new RangeError("something else");
      },
    });

    await expect(main(["chat"], dependencies)).rejects.toThrow(RangeError);
  });
});

describe("main chat", () => {
  const logs = useLogCapture();

  it("runs the REPL without needing GitHub credentials", async () => {
    const { sessionsRun, dependencies } = harness({
      buildGithubClient: () => {
        throw new MissingGitHubCredentialsError("no app id");
      },
    });

    await main(["chat"], dependencies);

    expect(sessionsRun).toHaveLength(1);
  });

  it("logs which command is running", async () => {
    const { dependencies } = harness();

    await main(["chat"], dependencies);

    expect(logs.contextOf("running chat")).toMatchObject({
      command: "chat",
      dry_run: false,
    });
  });

  it("prints the run and usage sections", async () => {
    const { stdout, dependencies } = harness();

    await main(["chat"], dependencies);

    expect(stripAnsi(stdout.text)).toContain("command   chat");
    expect(stripAnsi(stdout.text)).toContain("log       log/angel-");
    expect(stripAnsi(stdout.text)).toContain("Usage ");
    expect(stripAnsi(stdout.text)).toContain("calls");
  });
});

describe("main pr_review", () => {
  it("prints one line per pull request commented on", async () => {
    const { stdout, github, dependencies } = harness();
    labeledPullRequests(github, 1);

    await main(["pr_review"], dependencies);

    expect(stripAnsi(stdout.text)).toContain(`Commented on ${REPOSITORY}#1`);
    expect(github.postedComments).toHaveLength(1);
  });

  it("says so when nothing is due", async () => {
    const { stdout, github, dependencies } = harness();

    await main(["pr_review"], dependencies);

    expect(stdout.text).toContain("No pull requests to review");
    expect(github.postedComments).toEqual([]);
  });

  it("prints the review bodies and writes nothing under --dry-run", async () => {
    const { stdout, github, dependencies } = harness();
    labeledPullRequests(github, 1);

    await main(["pr_review", "--dry-run"], dependencies);

    expect(github.postedComments).toEqual([]);
    expect(github.ensureLabelCalls).toEqual([]);
    expect(stripAnsi(stdout.text)).toContain("dry run   yes");
    expect(stdout.text).toContain("fake summary");
  });

  it("exits non-zero and reports the failures on stderr", async () => {
    const { stdout, stderr, client, github, dependencies } = harness();
    labeledPullRequests(github, 1, 2, 3, 4, 5);
    client.failStructuredCall = 3;

    const error = await expectExit(main(["pr_review"], dependencies));

    expect(error.code).toBe(1);
    expect(error.message).toBe("1 of 5 items failed");
    expect(stripAnsi(stdout.text).match(/Commented on/g)).toHaveLength(4);
    expect(stripAnsi(stdout.text)).not.toContain(`${REPOSITORY}#1\n`);
    expect(stripAnsi(stderr.text)).toContain("Failed review_pull_requests");
  });

  it("still prints the usage section before exiting non-zero", async () => {
    const { stdout, client, github, dependencies } = harness();
    labeledPullRequests(github, 1);
    client.failStructuredCall = 1;

    await expectExit(main(["pr_review"], dependencies));

    expect(stripAnsi(stdout.text)).toContain("Usage ");
  });

  it("names a repository-level failure without an item number", async () => {
    const { stderr, github, dependencies } = harness();
    labeledPullRequests(github, 1);
    github.pullRequests["monalisa/broken"] = [];
    github.ensureLabel = async (repository) => {
      if (repository === "monalisa/broken") {
        throw new Error("403");
      }
    };

    const error = await expectExit(main(["pr_review"], dependencies));

    expect(stripAnsi(stderr.text)).toContain(
      "Failed fetch_pull_requests for monalisa/broken: Error: 403",
    );
    expect(error.message).toBe("1 of 2 items failed");
  });
});

describe("main issue_review", () => {
  it("prints one line per issue commented on", async () => {
    const { stdout, github, dependencies } = harness();
    labeledIssues(github, 1);

    await main(["issue_review"], dependencies);

    expect(stripAnsi(stdout.text)).toContain(`Commented on ${REPOSITORY}#1`);
  });

  it("says so when nothing is due", async () => {
    const { stdout, dependencies } = harness();

    await main(["issue_review"], dependencies);

    expect(stdout.text).toContain("No issues to review");
  });

  it("exits non-zero when a review fails", async () => {
    const { stdout, client, github, dependencies } = harness();
    labeledIssues(github, 1, 2, 3, 4, 5);
    client.failStructuredCall = 3;

    const error = await expectExit(main(["issue_review"], dependencies));

    expect(error.code).toBe(1);
    expect(stripAnsi(stdout.text).match(/Commented on/g)).toHaveLength(4);
    expect(stripAnsi(stdout.text)).not.toContain(`${REPOSITORY}#3`);
  });

  it("makes zero writes under --dry-run", async () => {
    const { github, dependencies } = harness();
    labeledIssues(github, 1);

    await main(["issue_review", "--dry-run"], dependencies);

    expect(github.postedComments).toEqual([]);
    expect(github.ensureLabelCalls).toEqual([]);
  });
});

describe("start", () => {
  useTemporaryDirectory();
  const previousExitCode = process.exitCode;

  afterEach(() => {
    process.exitCode = previousExitCode;
  });

  it("exits 0 and writes the help to stdout", async () => {
    const written: string[] = [];
    vi.spyOn(process.stdout, "write").mockImplementation((chunk) => {
      written.push(String(chunk));
      return true;
    });

    await start(["--help"]);

    expect(process.exitCode).toBe(0);
    expect(written.join("")).toContain("usage: angel");
  });

  it("writes the message to stderr and exits 1 on an unknown command", async () => {
    const written: string[] = [];
    vi.spyOn(process.stderr, "write").mockImplementation((chunk) => {
      written.push(String(chunk));
      return true;
    });

    await start(["bogus"]);

    expect(process.exitCode).toBe(1);
    expect(written.join("")).toContain("Unknown command: bogus.");
  });

  it("exits 1 when the real dependencies cannot be built", async () => {
    vi.spyOn(process.stdout, "write").mockReturnValue(true);
    vi.spyOn(process.stderr, "write").mockReturnValue(true);
    delete process.env.ANGEL_NVIDIA_API_KEY;
    resetEnvCache();

    await start(["chat"]);

    expect(process.exitCode).toBe(1);
  });
});
