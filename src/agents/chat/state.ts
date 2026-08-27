import { MessagesAnnotation } from "@langchain/langgraph";

/**
 * The conversation so far.
 *
 * `messages` accumulates through the `addMessages` reducer, so each turn appends
 * to the thread the checkpointer holds rather than replacing it.
 */
export const ChatAnnotation = MessagesAnnotation;

export type ChatState = typeof ChatAnnotation.State;
