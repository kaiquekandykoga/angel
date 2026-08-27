import { Annotation } from "@langchain/langgraph";
import type { Comment, PullRequest } from "../../external/github/client.js";
import type { ItemFailure, Review } from "../shared.js";

export interface PullRequestContext {
  readonly pullRequest: PullRequest;
  readonly comments: Comment[];
}

function replace<T>(_current: T, next: T): T {
  return next;
}

export const PrReviewAnnotation = Annotation.Root({
  pullRequests: Annotation<PullRequestContext[]>({
    reducer: replace,
    default: () => [],
  }),
  reviews: Annotation<Review[]>({ reducer: replace, default: () => [] }),
  failures: Annotation<ItemFailure[]>({
    reducer: (current, next) => [...current, ...next],
    default: () => [],
  }),
});

export type PrReviewState = typeof PrReviewAnnotation.State;
