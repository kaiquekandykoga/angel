import { END, START, StateGraph } from "@langchain/langgraph";
import { getLogger } from "../../../../packages/shared/logs.js";
import type { GitHubClient } from "../../external/github/client.js";
import type { LlmClient } from "../../external/nvidia/client.js";
import {
  postReviewComments,
  RETRY_POLICY,
  type ReviewGraphOptions,
  reviewSettings,
} from "../shared.js";
import { fetchPullRequests, reviewPullRequests } from "./nodes.js";
import { PrReviewAnnotation } from "./state.js";

const log = getLogger("angel.agents.pr-review.graph");

export function buildPrReviewGraph(
  client: LlmClient,
  github: GitHubClient,
  options: ReviewGraphOptions = {},
) {
  const { reviewerLogin, label, labelColor } = reviewSettings(options);
  log.debug("wiring pr_review graph nodes", { reviewer_login: reviewerLogin, label });
  const compiled = new StateGraph(PrReviewAnnotation)
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
    .addEdge("post_review_comments", END)
    .compile();
  log.info("pr_review graph ready");
  return compiled;
}
