import { Annotation } from "@langchain/langgraph";
import type { PullRequest } from "../../external/github/client.js";
import { contextChannel, type ReviewContext, reviewChannels } from "../shared.js";

export type PullRequestContext = ReviewContext<PullRequest>;

export const PrReviewAnnotation = Annotation.Root({
  pullRequests: contextChannel<PullRequest>(),
  ...reviewChannels(),
});

export type PrReviewState = typeof PrReviewAnnotation.State;
