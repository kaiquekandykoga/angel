import { randomUUID } from "node:crypto";
import { createInterface } from "node:readline/promises";
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

export interface ReplIo {
  readLine(prompt: string): Promise<string | undefined>;
  write(text: string): void;
  close?(): void;
}

export function terminalIo(): ReplIo {
  const readline = createInterface({ input: process.stdin, output: process.stdout });
  return {
    async readLine(prompt: string): Promise<string | undefined> {
      try {
        return await readline.question(prompt);
      } catch {
        return undefined;
      }
    },
    write(text: string): void {
      process.stdout.write(`${text}\n`);
    },
    close(): void {
      readline.close();
    },
  };
}

export async function run(session: Session, io: ReplIo): Promise<void> {
  try {
    while (true) {
      const line = await io.readLine("> ");
      if (line === undefined) {
        return;
      }
      const question = line.trim();
      if (question === "") {
        continue;
      }
      if (question === "/exit") {
        return;
      }
      io.write(await session.ask(question));
    }
  } finally {
    io.close?.();
  }
}
