import { buildChatGraph } from "./agents/chat/graph.js";
import {
  run as runRepl,
  type Session,
  startSession,
  terminalIo,
} from "./agents/chat/repl.js";
import { buildIssueReviewGraph } from "./agents/issue-review/graph.js";
import { buildPrReviewGraph } from "./agents/pr-review/graph.js";
import type { ItemFailure, Review } from "./agents/shared.js";
import { type Command, ExitError, parseArguments } from "./cli.js";
import {
  buildGithubClient,
  DryRunGitHubClient,
  type GitHubClient,
  MissingGitHubCredentialsError,
} from "./clients/github.js";
import {
  buildLlmClient,
  InvalidMaxCompletionTokensError,
  type LlmClient,
  MissingApiKeyError,
  resetUsage,
  usageTotals,
} from "./clients/llm.js";
import { BOLD, DIM, GREEN, type OutputStream, RED, section, style } from "./console.js";
import { configureLogging, getLogger } from "./logs.js";

const log = getLogger("angel.main");

export interface MainDependencies {
  readonly buildLlmClient: () => LlmClient;
  readonly buildGithubClient: () => GitHubClient;
  readonly runRepl: (session: Session) => Promise<void>;
  readonly configureLogging: () => string;
  readonly stdout: OutputStream;
  readonly stderr: OutputStream;
}

function defaultDependencies(): MainDependencies {
  return {
    buildLlmClient,
    buildGithubClient,
    runRepl: (session) => runRepl(session, terminalIo()),
    configureLogging: () => configureLogging(),
    stdout: process.stdout,
    stderr: process.stderr,
  };
}

function writeLine(stream: OutputStream, text = ""): void {
  stream.write(`${text}\n`);
}

function count(value: number): string {
  return value.toLocaleString("en-US").padStart(9);
}

function printRunSection(
  stream: OutputStream,
  command: Command,
  dryRun: boolean,
  logPath: string,
): void {
  section("Run", stream);
  writeLine(stream);
  writeLine(stream, `  ${"command".padEnd(7)}   ${command}`);
  writeLine(stream, `  ${"dry run".padEnd(7)}   ${dryRun ? "yes" : "no"}`);
  writeLine(stream, `  ${"log".padEnd(7)}   ${logPath}`);
}

function printUsageSection(stream: OutputStream): void {
  const totals = usageTotals();
  section("Usage", stream);
  writeLine(stream);
  writeLine(stream, `  ${"calls".padEnd(13)}${count(totals.calls)}`);
  writeLine(stream, `  ${"input_tokens".padEnd(13)}${count(totals.inputTokens)}`);
  writeLine(stream, `  ${"output_tokens".padEnd(13)}${count(totals.outputTokens)}`);
  writeLine(stream, `  ${"total_tokens".padEnd(13)}${count(totals.totalTokens)}`);
  writeLine(
    stream,
    `  ${"duration_ms".padEnd(13)}${totals.durationMs.toFixed(1).padStart(9)}`,
  );
}

function printReviews(
  stream: OutputStream,
  reviews: readonly Review[],
  dryRun: boolean,
  nothingMessage: string,
): void {
  section("Reviews", stream);
  writeLine(stream);
  if (reviews.length === 0) {
    writeLine(stream, style(nothingMessage, [DIM], stream));
    return;
  }
  for (const review of reviews) {
    const label = `${review.target.repository}#${review.target.number}`;
    if (dryRun) {
      writeLine(stream, style(label, [BOLD], stream));
      writeLine(stream, review.body);
      writeLine(stream);
    } else {
      writeLine(stream, style(`  Commented on ${label}`, [GREEN], stream));
    }
  }
}

export function reportFailures(
  stream: OutputStream,
  failures: readonly ItemFailure[],
  succeeded: number,
): void {
  if (failures.length === 0) {
    return;
  }
  section("Failures", stream);
  writeLine(stream);
  for (const failure of failures) {
    const target =
      failure.number === 0
        ? failure.repository
        : `${failure.repository}#${failure.number}`;
    writeLine(
      stream,
      style(
        `Failed ${failure.stage} for ${target}: ${failure.errorType}: ${failure.error}`,
        [RED],
        stream,
      ),
    );
  }
  const neverReviewed = failures.filter(
    (failure) => failure.stage !== "post_review_comments",
  ).length;
  throw new ExitError(
    1,
    `${failures.length} of ${succeeded + neverReviewed} items failed`,
  );
}

async function runChat(
  client: LlmClient,
  dependencies: MainDependencies,
): Promise<void> {
  const session = startSession(buildChatGraph(client));
  await dependencies.runRepl(session);
  printUsageSection(dependencies.stdout);
}

async function runPrReview(
  client: LlmClient,
  github: GitHubClient,
  dryRun: boolean,
  dependencies: MainDependencies,
): Promise<void> {
  const result = await buildPrReviewGraph(client, github).invoke({
    pullRequests: [],
    reviews: [],
    failures: [],
  });
  printReviews(
    dependencies.stdout,
    result.reviews,
    dryRun,
    "No pull requests to review",
  );
  printUsageSection(dependencies.stdout);
  reportFailures(dependencies.stderr, result.failures, result.reviews.length);
}

async function runIssueReview(
  client: LlmClient,
  github: GitHubClient,
  dryRun: boolean,
  dependencies: MainDependencies,
): Promise<void> {
  const result = await buildIssueReviewGraph(client, github).invoke({
    issues: [],
    reviews: [],
    failures: [],
  });
  printReviews(dependencies.stdout, result.reviews, dryRun, "No issues to review");
  printUsageSection(dependencies.stdout);
  reportFailures(dependencies.stderr, result.failures, result.reviews.length);
}

function buildClients(
  command: Command,
  dependencies: MainDependencies,
): { client: LlmClient; github: GitHubClient | undefined } {
  try {
    return {
      client: dependencies.buildLlmClient(),
      github: command === "chat" ? undefined : dependencies.buildGithubClient(),
    };
  } catch (error) {
    if (
      error instanceof MissingApiKeyError ||
      error instanceof InvalidMaxCompletionTokensError ||
      error instanceof MissingGitHubCredentialsError
    ) {
      throw new ExitError(1, error.message);
    }
    throw error;
  }
}

export async function main(
  argv: readonly string[],
  overrides: Partial<MainDependencies> = {},
): Promise<void> {
  const dependencies = { ...defaultDependencies(), ...overrides };
  const parsed = parseArguments(argv);
  if (parsed.kind === "help") {
    dependencies.stdout.write(parsed.text);
    throw new ExitError(0);
  }

  const { command, dryRun } = parsed.arguments;
  const logPath = dependencies.configureLogging();
  log.info(`running ${command}`, {
    command,
    log_path: logPath,
    dry_run: dryRun,
  });
  resetUsage();
  printRunSection(dependencies.stdout, command, dryRun, logPath);

  const { client, github } = buildClients(command, dependencies);
  if (github === undefined) {
    await runChat(client, dependencies);
    return;
  }

  const target = dryRun ? new DryRunGitHubClient(github) : github;
  if (command === "pr_review") {
    await runPrReview(client, target, dryRun, dependencies);
  } else {
    await runIssueReview(client, target, dryRun, dependencies);
  }
}

export async function cli(argv: readonly string[] = process.argv.slice(2)) {
  try {
    await main(argv);
  } catch (error) {
    if (error instanceof ExitError) {
      if (error.message !== "") {
        process.stderr.write(`${error.message}\n`);
      }
      process.exitCode = error.code;
      return;
    }
    throw error;
  }
}
