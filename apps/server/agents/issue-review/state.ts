import { Annotation } from "@langchain/langgraph";
import type { Issue } from "../../external/github/client.js";
import { contextChannel, type ReviewContext, reviewChannels } from "../shared.js";

export type IssueContext = ReviewContext<Issue>;

export const IssueReviewAnnotation = Annotation.Root({
  issues: contextChannel<Issue>(),
  ...reviewChannels(),
});

export type IssueReviewState = typeof IssueReviewAnnotation.State;
