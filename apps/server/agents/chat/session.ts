import { randomUUID } from "node:crypto";
import { HumanMessage } from "@langchain/core/messages";
import type { ChatGraph } from "./graph.js";

export interface Session {
  ask(question: string): Promise<string>;
}

export class ChatSession implements Session {
  constructor(
    private readonly graph: ChatGraph,
    readonly threadId: string,
  ) {}

  async ask(question: string): Promise<string> {
    const result = await this.graph.invoke(
      { messages: [new HumanMessage(question)] },
      { configurable: { thread_id: this.threadId } },
    );
    const reply = result.messages.at(-1);
    return typeof reply?.content === "string" ? reply.content : "";
  }
}

export function startSession(graph: ChatGraph): ChatSession {
  return new ChatSession(graph, randomUUID());
}
