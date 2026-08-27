import { MessagesAnnotation } from "@langchain/langgraph";

export const ChatAnnotation = MessagesAnnotation;

export type ChatState = typeof ChatAnnotation.State;
