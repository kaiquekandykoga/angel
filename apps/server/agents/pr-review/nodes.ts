import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import { getLogger } from "../../../../packages/shared/logs.js";
import type { GitHubClient } from "../../external/github/client.js";
import type { LlmClient } from "../../external/nvidia/client.js";
import {
  fenceUntrusted,
  finalizeReviewBody,
  lastReviewAt,
  logReviewProduced,
  PULL_REQUEST_REVIEW_OUTPUT,
  type PullRequestReviewOutput,
  renderComments,
  renderFindings,
  reviewedSha,
  reviewMarker,
  reviewTargets,
  scanTargets,
} from "../shared.js";
import { filterDiff, renderOmissions } from "./diff.js";
import { REVIEW_LENSES } from "./prompts.js";
import type { PrReviewState } from "./state.js";

const log = getLogger("angel.agents.pr-review.nodes");

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
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
        `### ${capitalize(lens)}\n\n${renderFindings(output.findings)}`,
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
  return async () => {
    const { contexts, failures } = await scanTargets(log, github, {
      stage: "fetch_pull_requests",
      noun: "pull request",
      plural: "pull requests",
      label,
      labelColor,
      list: (repository) => github.listOpenPullRequests(repository, label),
      select: (pullRequest, comments) => {
        const recordedSha = reviewedSha(comments, reviewerLogin);
        if (lastReviewAt(comments, reviewerLogin) === undefined) {
          return { selected: true, reason: "never reviewed" };
        }
        if (recordedSha === undefined) {
          return { selected: true, reason: "no recorded head" };
        }
        if (recordedSha !== pullRequest.headSha) {
          return { selected: true, reason: "new head" };
        }
        return { selected: false, reason: "already up to date" };
      },
    });
    return { pullRequests: contexts, failures };
  };
}

export function reviewPullRequests(github: GitHubClient, client: LlmClient) {
  return async (state: Pick<PrReviewState, "pullRequests">) =>
    reviewTargets(log, state.pullRequests, {
      stage: "review_pull_requests",
      noun: "pull request",
      plural: "pull requests",
      body: async ({ target, comments }) => {
        const diff = filterDiff(await github.fetchDiff(target));
        const content =
          `Repository: ${target.repository}\n` +
          `Pull request #${target.number}\n\n` +
          `Title:\n${fenceUntrusted("pull_request_title", target.title)}\n\n` +
          `Description:\n${fenceUntrusted("pull_request_body", target.body)}\n\n` +
          "Existing comments:\n" +
          `${fenceUntrusted("pull_request_comments", renderComments(comments))}\n\n` +
          "Diff:\n" +
          fenceUntrusted(
            "pull_request_diff",
            `${diff.text}${renderOmissions(diff.skipped)}`,
          );
        log.debug("reviewing pull request", {
          repository: target.repository,
          number: target.number,
          diff_size: diff.bytes,
          diff_size_original: diff.originalBytes,
          diff_files_included: diff.includedFiles,
          diff_files_skipped: diff.skipped.length,
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
            repository: target.repository,
            number: target.number,
            review: `${output.summary}\n\n${renderFindings(output.findings)}`,
            findings: output.findings,
            lens: lens.name,
          });
        }

        return finalizeReviewBody(
          renderMergedReview(lensOutputs),
          reviewMarker(target.headSha),
        );
      },
    });
}
