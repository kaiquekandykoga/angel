import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import { getLogger } from "../../../../packages/shared/logs.js";
import type { GitHubClient } from "../../external/github/client.js";
import type { LlmClient } from "../../external/nvidia/client.js";
import {
  collectFailures,
  type Finding,
  type ItemFailure,
  lastReviewAt,
  logReviewProduced,
  PULL_REQUEST_REVIEW_OUTPUT,
  type PullRequestReviewOutput,
  type Review,
  renderComments,
  renderFinding,
  reviewedSha,
  reviewMarker,
} from "../shared.js";
import { REVIEW_LENSES } from "./prompts.js";
import type { PrReviewState, PullRequestContext } from "./state.js";

const log = getLogger("angel.agents.pr-review.nodes");

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function renderLensFindings(findings: readonly Finding[]): string {
  if (findings.length === 0) {
    return "No findings.";
  }
  return findings.map(renderFinding).join("\n\n");
}

function renderLensReview(output: PullRequestReviewOutput): string {
  return `${output.summary}\n\n${renderLensFindings(output.findings)}`;
}

interface LensOutput {
  readonly lens: string;
  readonly output: PullRequestReviewOutput;
}

export function renderMergedReview(lensOutputs: readonly LensOutput[]): string {
  const summary = lensOutputs
    .map(({ lens, output }) => `**${capitalize(lens)}:** ${output.summary}`)
    .join("\n\n");
  const sections = lensOutputs
    .map(
      ({ lens, output }) =>
        `### ${capitalize(lens)}\n\n${renderLensFindings(output.findings)}`,
    )
    .join("\n\n");
  return `${summary}\n\n${sections}`;
}

export function fetchPullRequests(
  github: GitHubClient,
  reviewerLogin: string,
  label: string,
  labelColor: string,
) {
  return async (): Promise<{
    pullRequests: PullRequestContext[];
    failures: ItemFailure[];
  }> => {
    log.info("fetching pull requests");
    const pullRequests: PullRequestContext[] = [];
    const failures: ItemFailure[] = [];
    const repositories = await github.listRepositories();
    let itemsScanned = 0;

    for (const repository of repositories) {
      await collectFailures(
        failures,
        "failed to fetch pull requests for repository",
        { stage: "fetch_pull_requests", repository, number: 0 },
        async () => {
          await github.ensureLabel(repository, label, labelColor);
          const labeled = await github.listOpenPullRequests(repository, label);
          log.debug("scanning repository", {
            repository,
            labeled_items_found: labeled.length,
          });
          for (const pullRequest of labeled) {
            itemsScanned += 1;
            await collectFailures(
              failures,
              "failed to fetch pull request",
              {
                stage: "fetch_pull_requests",
                repository: pullRequest.repository,
                number: pullRequest.number,
              },
              async () => {
                const comments = await github.listComments(pullRequest);
                const recordedSha = reviewedSha(comments, reviewerLogin);
                let selected: boolean;
                let reason: string;
                if (lastReviewAt(comments, reviewerLogin) === undefined) {
                  [selected, reason] = [true, "never reviewed"];
                } else if (recordedSha === undefined) {
                  [selected, reason] = [true, "no recorded head"];
                } else if (recordedSha !== pullRequest.headSha) {
                  [selected, reason] = [true, "new head"];
                } else {
                  [selected, reason] = [false, "already up to date"];
                }
                log.debug("evaluated pull request", {
                  repository: pullRequest.repository,
                  number: pullRequest.number,
                  selected,
                  reason,
                });
                if (selected) {
                  pullRequests.push({ pullRequest, comments });
                }
              },
            );
          }
        },
      );
    }

    log.info("pull requests fetched", {
      repositories_scanned: repositories.length,
      items_scanned: itemsScanned,
      items_due_for_review: pullRequests.length,
    });
    return { pullRequests, failures };
  };
}

export function reviewPullRequests(github: GitHubClient, client: LlmClient) {
  return async (
    state: Pick<PrReviewState, "pullRequests">,
  ): Promise<{ reviews: Review[]; failures: ItemFailure[] }> => {
    const contexts = state.pullRequests;
    log.info(`reviewing ${contexts.length} pull requests`);
    const reviews: Review[] = [];
    const failures: ItemFailure[] = [];

    for (const context of contexts) {
      const { pullRequest } = context;
      await collectFailures(
        failures,
        "failed to review pull request",
        {
          stage: "review_pull_requests",
          repository: pullRequest.repository,
          number: pullRequest.number,
        },
        async () => {
          const diff = await github.fetchDiff(pullRequest);
          const content =
            `Repository: ${pullRequest.repository}\n` +
            `Pull request #${pullRequest.number}: ${pullRequest.title}\n\n` +
            `Description:\n${pullRequest.body}\n\n` +
            `Existing comments:\n${renderComments(context.comments)}\n\n` +
            `Diff:\n${diff}`;
          log.debug("reviewing pull request", {
            repository: pullRequest.repository,
            number: pullRequest.number,
            diff_size: diff.length,
            prompt_message_count: 2,
            lens_count: REVIEW_LENSES.length,
          });

          const lensOutputs: LensOutput[] = [];
          for (const lens of REVIEW_LENSES) {
            const output = await client.completeStructured(
              [new SystemMessage(lens.prompt), new HumanMessage(content)],
              PULL_REQUEST_REVIEW_OUTPUT,
            );
            lensOutputs.push({ lens: lens.name, output });
            logReviewProduced(log, {
              repository: pullRequest.repository,
              number: pullRequest.number,
              review: renderLensReview(output),
              findings: output.findings,
              lens: lens.name,
            });
          }

          log.info(`reviewed ${pullRequest.repository}#${pullRequest.number}`, {
            repository: pullRequest.repository,
            number: pullRequest.number,
          });
          reviews.push({
            target: pullRequest,
            body: `${renderMergedReview(lensOutputs)}\n\n${reviewMarker(
              pullRequest.headSha,
            )}`,
          });
        },
      );
    }

    log.info("pull requests reviewed", { count: reviews.length });
    return { reviews, failures };
  };
}
