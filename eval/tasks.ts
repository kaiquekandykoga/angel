import { CallbackHandler } from "@langfuse/langchain";
import {
  buildIssueReviewGraph,
  buildPrReviewGraph,
  type Finding,
  ISSUE_REVIEW_OUTPUT,
  type IssueReviewOutput,
  type ItemFailure,
  type LlmClient,
  PULL_REQUEST_REVIEW_OUTPUT,
  type PullRequestReviewOutput,
} from "../apps/server/index.js";
import type { IssueReviewInput, PrReviewInput } from "./datasets.js";
import { StaticGitHubClient } from "./github.js";
import { RecordingLlmClient } from "./llm.js";

export interface PrReviewResult {
  readonly body: string;
  readonly findings: readonly Finding[];
  readonly lenses: readonly PullRequestReviewOutput[];
}

export interface IssueReviewResult {
  readonly body: string;
  readonly findings: readonly Finding[];
  readonly output: IssueReviewOutput;
}

class ReviewFailedError extends Error {
  override readonly name = "ReviewFailedError";
}

function ensureReviewed(body: string | undefined, failures: ItemFailure[]): string {
  if (failures.length > 0) {
    const reasons = failures
      .map((failure) => `${failure.stage}: ${failure.errorType}: ${failure.error}`)
      .join("; ");
    throw new ReviewFailedError(reasons);
  }
  if (body === undefined) {
    throw new ReviewFailedError("the graph produced no review");
  }
  return body;
}

export async function runPrReview(
  input: PrReviewInput,
  client: LlmClient,
): Promise<PrReviewResult> {
  const pullRequest = {
    repository: input.repository,
    number: input.number,
    title: input.title,
    body: input.body,
    headSha: input.headSha,
  };
  const github = new StaticGitHubClient({
    repository: input.repository,
    pullRequests: [pullRequest],
    issues: [],
    diffs: new Map([[input.number, input.diff]]),
    comments: new Map([[input.number, input.comments]]),
  });
  const recorder = new RecordingLlmClient(client);

  const state = await buildPrReviewGraph(recorder, github).invoke(
    {},
    { callbacks: [new CallbackHandler()] },
  );

  const lenses = recorder.outputsFor(PULL_REQUEST_REVIEW_OUTPUT);
  return {
    body: ensureReviewed(state.reviews.at(0)?.body, state.failures),
    findings: lenses.flatMap((lens) => lens.findings),
    lenses,
  };
}

export async function runIssueReview(
  input: IssueReviewInput,
  client: LlmClient,
): Promise<IssueReviewResult> {
  const issue = {
    repository: input.repository,
    number: input.number,
    title: input.title,
    body: input.body,
    updatedAt: input.updatedAt,
  };
  const github = new StaticGitHubClient({
    repository: input.repository,
    pullRequests: [],
    issues: [issue],
    diffs: new Map(),
    comments: new Map([[input.number, input.comments]]),
  });
  const recorder = new RecordingLlmClient(client);

  const state = await buildIssueReviewGraph(recorder, github).invoke(
    {},
    { callbacks: [new CallbackHandler()] },
  );

  const body = ensureReviewed(state.reviews.at(0)?.body, state.failures);
  const output = recorder.outputsFor(ISSUE_REVIEW_OUTPUT).at(0);
  if (output === undefined) {
    throw new ReviewFailedError("the model was never called");
  }
  return { body, findings: output.findings, output };
}
