import { Annotation } from "@langchain/langgraph";
import type { Comment, Issue } from "../../clients/github.js";
import type { ItemFailure, Review } from "../shared.js";

/** An issue due for review, with the comments that decided it. */
export interface IssueContext {
  readonly issue: Issue;
  readonly comments: Comment[];
}

function replace<T>(_current: T, next: T): T {
  return next;
}

export const IssueReviewAnnotation = Annotation.Root({
  issues: Annotation<IssueContext[]>({ reducer: replace, default: () => [] }),
  reviews: Annotation<Review[]>({ reducer: replace, default: () => [] }),
  /** Accumulates rather than clobbers, because every node writes to it. */
  failures: Annotation<ItemFailure[]>({
    reducer: (current, next) => [...current, ...next],
    default: () => [],
  }),
});

export type IssueReviewState = typeof IssueReviewAnnotation.State;
