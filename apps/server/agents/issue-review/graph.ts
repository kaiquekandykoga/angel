import { END, START, StateGraph } from "@langchain/langgraph";
import { getLogger } from "../../../../packages/shared/logs.js";
import type { LlmClient } from "../../clients/llm.js";
import type { GitHubClient } from "../../external/github/client.js";
import { LABEL, LABEL_COLOR, REVIEWER_LOGIN } from "../../external/github/settings.js";
import { postReviewComments } from "../shared.js";
import { fetchIssues, reviewIssues } from "./nodes.js";
import { IssueReviewAnnotation } from "./state.js";

const log = getLogger("angel.agents.issue-review.graph");

const RETRY_POLICY = { maxAttempts: 3 };

export interface IssueReviewGraphOptions {
  readonly reviewerLogin?: string;
  readonly label?: string;
  readonly labelColor?: string;
}

export function buildIssueReviewGraph(
  client: LlmClient,
  github: GitHubClient,
  options: IssueReviewGraphOptions = {},
) {
  const reviewerLogin = options.reviewerLogin ?? REVIEWER_LOGIN;
  const label = options.label ?? LABEL;
  const labelColor = options.labelColor ?? LABEL_COLOR;

  log.debug("wiring issue_review graph nodes", {
    reviewer_login: reviewerLogin,
    label,
  });
  const graph = new StateGraph(IssueReviewAnnotation)
    .addNode("fetch_issues", fetchIssues(github, reviewerLogin, label, labelColor), {
      retryPolicy: RETRY_POLICY,
    })
    .addNode("review_issues", reviewIssues(client), { retryPolicy: RETRY_POLICY })
    .addNode("post_review_comments", postReviewComments(github), {
      retryPolicy: RETRY_POLICY,
    })
    .addEdge(START, "fetch_issues")
    .addEdge("fetch_issues", "review_issues")
    .addEdge("review_issues", "post_review_comments")
    .addEdge("post_review_comments", END);

  const compiled = graph.compile();
  log.info("issue_review graph ready");
  return compiled;
}
