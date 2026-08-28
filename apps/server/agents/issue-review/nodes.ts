import { HumanMessage, SystemMessage } from "@langchain/core/messages";
import { getLogger } from "../../../../packages/shared/logs.js";
import type { GitHubClient } from "../../external/github/client.js";
import type { LlmClient } from "../../external/nvidia/client.js";
import {
  ISSUE_REVIEW_OUTPUT,
  lastReviewAt,
  logReviewProduced,
  renderComments,
  renderIssueReview,
  reviewTargets,
  scanTargets,
} from "../shared.js";
import { REVIEW_SYSTEM_PROMPT } from "./prompts.js";
import type { IssueReviewState } from "./state.js";

const log = getLogger("angel.agents.issue-review.nodes");

export function fetchIssues(
  github: GitHubClient,
  reviewerLogin: string,
  label: string,
  labelColor: string,
) {
  return async () => {
    const { contexts, failures } = await scanTargets(log, github, {
      stage: "fetch_issues",
      noun: "issue",
      plural: "issues",
      label,
      labelColor,
      list: (repository) => github.listOpenIssues(repository, label),
      select: (issue, comments) => {
        const lastReview = lastReviewAt(comments, reviewerLogin);
        if (lastReview === undefined) {
          return { selected: true, reason: "never reviewed" };
        }
        if (issue.updatedAt > lastReview) {
          return { selected: true, reason: "updated since last review" };
        }
        return { selected: false, reason: "already up to date" };
      },
    });
    return { issues: contexts, failures };
  };
}

export function reviewIssues(client: LlmClient) {
  return async (state: Pick<IssueReviewState, "issues">) =>
    reviewTargets(log, state.issues, {
      stage: "review_issues",
      noun: "issue",
      plural: "issues",
      body: async ({ target, comments }) => {
        const messages = [
          new SystemMessage(REVIEW_SYSTEM_PROMPT),
          new HumanMessage(
            `Repository: ${target.repository}\n` +
              `Issue #${target.number}: ${target.title}\n\n` +
              `Body:\n${target.body}\n\n` +
              `Existing comments:\n${renderComments(comments)}`,
          ),
        ];
        log.debug("reviewing issue", {
          repository: target.repository,
          number: target.number,
          prompt_message_count: messages.length,
        });

        const output = await client.completeStructured(messages, ISSUE_REVIEW_OUTPUT);
        const body = renderIssueReview(output);
        logReviewProduced(log, {
          repository: target.repository,
          number: target.number,
          review: body,
          findings: output.findings,
        });
        return body;
      },
    });
}
