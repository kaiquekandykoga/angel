import type { OutputStream } from "../../packages/shared/console.js";
import { configureLogging, getLogger } from "../../packages/shared/logs.js";
import {
  buildChatGraph,
  buildGithubClient,
  buildIssueReviewGraph,
  buildLlmClient,
  buildPrReviewGraph,
  dryRunClient,
  type GitHubClient,
  InvalidMaxCompletionTokensError,
  type ItemFailure,
  type LlmClient,
  MissingApiKeyError,
  MissingGitHubCredentialsError,
  resetUsage,
  type Session,
  startSession,
  usageTotals,
} from "../server/index.js";
import { run as runRepl, terminalIo } from "./repl.js";
import { type Command, ExitError, parseArguments, terminalUi, type Ui } from "./ui.js";

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

function reportFailures(
  ui: Ui,
  failures: readonly ItemFailure[],
  succeeded: number,
): void {
  if (failures.length === 0) {
    return;
  }
  ui.failures(failures);
  const neverReviewed = failures.filter(
    (failure) => failure.stage !== "post_review_comments",
  ).length;
  throw new ExitError(
    1,
    `${failures.length} of ${succeeded + neverReviewed} items failed`,
  );
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
  const ui = terminalUi(dependencies.stdout, dependencies.stderr);
  const logPath = dependencies.configureLogging();
  log.info(`running ${command}`, { command, log_path: logPath, dry_run: dryRun });
  resetUsage();
  ui.run(command, dryRun, logPath);

  const { client, github } = buildClients(command, dependencies);
  if (github === undefined) {
    await dependencies.runRepl(startSession(buildChatGraph(client)));
    ui.usage(usageTotals());
    return;
  }

  const target = dryRun ? dryRunClient(github) : github;
  const isPullRequests = command === "pr_review";
  const { reviews, failures } = isPullRequests
    ? await buildPrReviewGraph(client, target).invoke({})
    : await buildIssueReviewGraph(client, target).invoke({});

  ui.reviews(
    reviews,
    dryRun,
    isPullRequests ? "No pull requests to review" : "No issues to review",
  );
  ui.usage(usageTotals());
  reportFailures(ui, failures, reviews.length);
}

export async function start(argv: readonly string[] = process.argv.slice(2)) {
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
