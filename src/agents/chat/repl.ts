import { randomUUID } from "node:crypto";
import { createInterface } from "node:readline/promises";
import { HumanMessage } from "@langchain/core/messages";
import type { ChatGraph } from "./graph.js";

/** One question, one answer, against a thread that remembers the last ones. */
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

/** Starts a session on a fresh thread. */
export function startSession(graph: ChatGraph): ChatSession {
  return new ChatSession(graph, randomUUID());
}

/** Where the REPL reads lines from and writes replies to. */
export interface ReplIo {
  /** The next line, or `undefined` at end of input. */
  readLine(prompt: string): Promise<string | undefined>;
  write(text: string): void;
  close?(): void;
}

/** A {@link ReplIo} over stdin and stdout. */
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

/** Reads a line at a time until `/exit` or end of input. */
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
