import { Annotation } from "@langchain/langgraph";
import type { Comment, PullRequest } from "../../clients/github.js";
import type { ItemFailure, Review } from "../shared.js";

/** A pull request due for review, with the comments that decided it. */
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
  /** Accumulates rather than clobbers, because every node writes to it. */
  failures: Annotation<ItemFailure[]>({
    reducer: (current, next) => [...current, ...next],
    default: () => [],
  }),
});

export type PrReviewState = typeof PrReviewAnnotation.State;
