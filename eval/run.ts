import {
  buildLlmClient,
  InvalidMaxCompletionTokensError,
  type LlmClient,
  MissingApiKeyError,
  REVIEW_LENSES,
  resetUsage,
  usageTotals,
} from "../apps/server/index.js";
import {
  type ExpectedReview,
  ISSUE_REVIEW_ITEMS,
  type IssueReviewInput,
  issueReviewInputSchema,
  PR_REVIEW_ITEMS,
  type PrReviewInput,
  prReviewInputSchema,
} from "./datasets.js";
import {
  MissingLangfuseCredentialsError,
  startTracing,
  type Tracing,
} from "./langfuse.js";
import {
  acceptanceCriteriaCount,
  citedFilesInDiff,
  citedLinesInHunks,
  expectedFilesFlagged,
  expectedKeywordsMentioned,
  findingCount,
  lensesCovered,
  type Score,
  suggestedApproachPresent,
} from "./scorers.js";
import {
  type IssueReviewResult,
  type PrReviewResult,
  runIssueReview,
  runPrReview,
} from "./tasks.js";

const AGENTS = ["pr_review", "issue_review"] as const;

type Agent = (typeof AGENTS)[number];

const LENS_NAMES = REVIEW_LENSES.map((lens) => lens.name);

const NO_EXPECTATIONS: ExpectedReview = { files: [], keywords: [] };

export class UnknownAgentError extends Error {
  override readonly name = "UnknownAgentError";
}

export function parseAgents(argv: readonly string[]): Agent[] {
  if (argv.length === 0) {
    return [...AGENTS];
  }
  return argv.map((argument) => {
    const agent = AGENTS.find((candidate) => candidate === argument);
    if (agent === undefined) {
      throw new UnknownAgentError(
        `Unknown agent: ${argument}. Valid agents: ${AGENTS.join(", ")}`,
      );
    }
    return agent;
  });
}

export async function gradePrReview(params: {
  input: PrReviewInput;
  output: PrReviewResult;
  expectedOutput?: ExpectedReview;
}): Promise<Score[]> {
  const { input, output } = params;
  const expected = params.expectedOutput ?? NO_EXPECTATIONS;
  return [
    ...citedFilesInDiff(output.findings, input.diff),
    ...citedLinesInHunks(output.findings, input.diff),
    ...expectedFilesFlagged(output.findings, expected.files),
    ...expectedKeywordsMentioned(output.body, expected.keywords),
    ...lensesCovered(output.body, LENS_NAMES),
    findingCount(output.findings),
  ];
}

export async function gradeIssueReview(params: {
  output: IssueReviewResult;
  expectedOutput?: ExpectedReview;
}): Promise<Score[]> {
  const { output } = params;
  const expected = params.expectedOutput ?? NO_EXPECTATIONS;
  return [
    ...expectedKeywordsMentioned(output.body, expected.keywords),
    acceptanceCriteriaCount(output.output),
    suggestedApproachPresent(output.output),
    findingCount(output.findings),
  ];
}

async function runAgent(
  agent: Agent,
  client: LlmClient,
  tracing: Tracing,
): Promise<boolean> {
  const description = `Deterministic code evaluations for the ${agent} agent`;
  const result =
    agent === "pr_review"
      ? await tracing.client.experiment.run<PrReviewInput, ExpectedReview>({
          name: agent,
          description,
          data: [...PR_REVIEW_ITEMS],
          task: async (item) =>
            await runPrReview(prReviewInputSchema.parse(item.input), client),
          evaluators: [gradePrReview],
          maxConcurrency: 1,
        })
      : await tracing.client.experiment.run<IssueReviewInput, ExpectedReview>({
          name: agent,
          description,
          data: [...ISSUE_REVIEW_ITEMS],
          task: async (item) =>
            await runIssueReview(issueReviewInputSchema.parse(item.input), client),
          evaluators: [gradeIssueReview],
          maxConcurrency: 1,
        });

  const expected =
    agent === "pr_review" ? PR_REVIEW_ITEMS.length : ISSUE_REVIEW_ITEMS.length;
  process.stdout.write(`${await result.format({ includeItemResults: true })}\n`);
  if (result.itemResults.length < expected) {
    process.stderr.write(
      `${expected - result.itemResults.length} of ${expected} ${agent} items failed\n`,
    );
    return false;
  }
  return true;
}

export async function main(argv: readonly string[]): Promise<number> {
  const agents = parseAgents(argv);
  const client = buildLlmClient();
  const tracing = startTracing();
  process.stdout.write(`Reporting to ${tracing.baseUrl}\n`);
  resetUsage();
  try {
    let ok = true;
    for (const agent of agents) {
      ok = (await runAgent(agent, client, tracing)) && ok;
    }
    const usage = usageTotals();
    process.stdout.write(
      `Usage: ${usage.calls} calls, ${usage.totalTokens} tokens, ` +
        `${Math.round(usage.durationMs)} ms\n`,
    );
    return ok ? 0 : 1;
  } finally {
    await tracing.shutdown();
  }
}

export async function start(
  argv: readonly string[] = process.argv.slice(2),
): Promise<void> {
  try {
    process.exitCode = await main(argv);
  } catch (error) {
    if (
      error instanceof UnknownAgentError ||
      error instanceof MissingApiKeyError ||
      error instanceof InvalidMaxCompletionTokensError ||
      error instanceof MissingLangfuseCredentialsError
    ) {
      process.stderr.write(`${error.message}\n`);
      process.exitCode = 1;
      return;
    }
    throw error;
  }
}
