import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import type { GitHubClient } from "../../clients/github.js";
import type { LlmClient } from "../../clients/llm.js";
import { getLogger } from "../../logs.js";
import {
  collectFailures,
  ISSUE_REVIEW_OUTPUT,
  type ItemFailure,
  lastReviewAt,
  logReviewProduced,
  type Review,
  renderComments,
  renderIssueReview,
} from "../shared.js";
import { REVIEW_SYSTEM_PROMPT } from "./prompts.js";
import type { IssueContext, IssueReviewState } from "./state.js";

const log = getLogger("angel.agents.issue-review.nodes");

/**
 * Discovers every repository the App can reach and keeps the labeled issues due
 * for review: never reviewed, or edited since the last review.
 */
export function fetchIssues(
  github: GitHubClient,
  reviewerLogin: string,
  label: string,
  labelColor: string,
) {
  return async (): Promise<{ issues: IssueContext[]; failures: ItemFailure[] }> => {
    log.info("fetching issues");
    const issues: IssueContext[] = [];
    const failures: ItemFailure[] = [];
    const repositories = await github.listRepositories();
    let itemsScanned = 0;

    for (const repository of repositories) {
      await collectFailures(
        failures,
        "failed to fetch issues for repository",
        { stage: "fetch_issues", repository, number: 0 },
        async () => {
          await github.ensureLabel(repository, label, labelColor);
          const labeled = await github.listOpenIssues(repository, label);
          log.debug("scanning repository", {
            repository,
            labeled_items_found: labeled.length,
          });
          for (const issue of labeled) {
            itemsScanned += 1;
            await collectFailures(
              failures,
              "failed to fetch issue",
              {
                stage: "fetch_issues",
                repository: issue.repository,
                number: issue.number,
              },
              async () => {
                const comments = await github.listComments(issue);
                const lastReview = lastReviewAt(comments, reviewerLogin);
                let selected: boolean;
                let reason: string;
                if (lastReview === undefined) {
                  [selected, reason] = [true, "never reviewed"];
                } else if (issue.updatedAt > lastReview) {
                  [selected, reason] = [true, "updated since last review"];
                } else {
                  [selected, reason] = [false, "already up to date"];
                }
                log.debug("evaluated issue", {
                  repository: issue.repository,
                  number: issue.number,
                  selected,
                  reason,
                });
                if (selected) {
                  issues.push({ issue, comments });
                }
              },
            );
          }
        },
      );
    }

    log.info("issues fetched", {
      repositories_scanned: repositories.length,
      items_scanned: itemsScanned,
      items_due_for_review: issues.length,
    });
    return { issues, failures };
  };
}

/** Asks the model for one structured review per issue and renders it. */
export function reviewIssues(client: LlmClient) {
  return async (
    state: Pick<IssueReviewState, "issues">,
  ): Promise<{ reviews: Review[]; failures: ItemFailure[] }> => {
    const contexts = state.issues;
    log.info(`reviewing ${contexts.length} issues`);
    const reviews: Review[] = [];
    const failures: ItemFailure[] = [];

    for (const context of contexts) {
      const { issue } = context;
      await collectFailures(
        failures,
        "failed to review issue",
        {
          stage: "review_issues",
          repository: issue.repository,
          number: issue.number,
        },
        async () => {
          const messages = [
            new SystemMessage(REVIEW_SYSTEM_PROMPT),
            new HumanMessage(
              `Repository: ${issue.repository}\n` +
                `Issue #${issue.number}: ${issue.title}\n\n` +
                `Body:\n${issue.body}\n\n` +
                `Existing comments:\n${renderComments(context.comments)}`,
            ),
          ];
          log.debug("reviewing issue", {
            repository: issue.repository,
            number: issue.number,
            prompt_message_count: messages.length,
          });

          const output = await client.completeStructured(messages, ISSUE_REVIEW_OUTPUT);
          const body = renderIssueReview(output);
          logReviewProduced(log, {
            repository: issue.repository,
            number: issue.number,
            review: body,
            findings: output.findings,
          });
          log.info(`reviewed ${issue.repository}#${issue.number}`, {
            repository: issue.repository,
            number: issue.number,
          });
          reviews.push({ target: issue, body });
        },
      );
    }

    log.info("issues reviewed", { count: reviews.length });
    return { reviews, failures };
  };
}
