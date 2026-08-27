import { createInterface } from "node:readline/promises";
import type { Session } from "../server/index.js";

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
