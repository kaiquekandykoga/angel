import { END, START, StateGraph } from "@langchain/langgraph";
import { getLogger } from "../../../../packages/shared/logs.js";
import type { LlmClient } from "../../clients/llm.js";
import type { GitHubClient } from "../../external/github/client.js";
import { LABEL, LABEL_COLOR, REVIEWER_LOGIN } from "../../external/github/settings.js";
import { postReviewComments } from "../shared.js";
import { fetchPullRequests, reviewPullRequests } from "./nodes.js";
import { PrReviewAnnotation } from "./state.js";

const log = getLogger("angel.agents.pr-review.graph");

const RETRY_POLICY = { maxAttempts: 3 };

export interface PrReviewGraphOptions {
  readonly reviewerLogin?: string;
  readonly label?: string;
  readonly labelColor?: string;
}

export function buildPrReviewGraph(
  client: LlmClient,
  github: GitHubClient,
  options: PrReviewGraphOptions = {},
) {
  const reviewerLogin = options.reviewerLogin ?? REVIEWER_LOGIN;
  const label = options.label ?? LABEL;
  const labelColor = options.labelColor ?? LABEL_COLOR;

  log.debug("wiring pr_review graph nodes", { reviewer_login: reviewerLogin, label });
  const graph = new StateGraph(PrReviewAnnotation)
    .addNode(
      "fetch_pull_requests",
      fetchPullRequests(github, reviewerLogin, label, labelColor),
      { retryPolicy: RETRY_POLICY },
    )
    .addNode("review_pull_requests", reviewPullRequests(github, client), {
      retryPolicy: RETRY_POLICY,
    })
    .addNode("post_review_comments", postReviewComments(github), {
      retryPolicy: RETRY_POLICY,
    })
    .addEdge(START, "fetch_pull_requests")
    .addEdge("fetch_pull_requests", "review_pull_requests")
    .addEdge("review_pull_requests", "post_review_comments")
    .addEdge("post_review_comments", END);

  const compiled = graph.compile();
  log.info("pr_review graph ready");
  return compiled;
}
