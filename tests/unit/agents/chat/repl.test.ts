import { SystemMessage } from "@langchain/core/messages";
import { describe, expect, it } from "vitest";
import { buildChatGraph } from "../../../../src/agents/chat/graph.js";
import {
  type ReplIo,
  run,
  type Session,
  startSession,
} from "../../../../src/agents/chat/repl.js";
import { contentsOf, FakeLlmClient } from "../../../helpers/llm.js";

class FakeSession implements Session {
  readonly questions: string[] = [];

  async ask(question: string): Promise<string> {
    this.questions.push(question);
    return `answer to ${question}`;
  }
}

function scriptedIo(
  ...lines: string[]
): ReplIo & { written: string[]; closed: boolean } {
  const remaining = [...lines];
  const io = {
    written: [] as string[],
    closed: false,
    async readLine(): Promise<string | undefined> {
      return remaining.shift();
    },
    write(text: string): void {
      io.written.push(text);
    },
    close(): void {
      io.closed = true;
    },
  };
  return io;
}

describe("run", () => {
  it("answers a line and stops at end of input", async () => {
    const session = new FakeSession();
    const io = scriptedIo("hello");

    await run(session, io);

    expect(session.questions).toEqual(["hello"]);
    expect(io.written).toEqual(["answer to hello"]);
  });

  it("stops at /exit without asking anything more", async () => {
    const session = new FakeSession();
    const io = scriptedIo("/exit", "should not be reached");

    await run(session, io);

    expect(session.questions).toEqual([]);
    expect(io.written).toEqual([]);
  });

  it("forwards bare exit and quit as ordinary questions", async () => {
    const session = new FakeSession();

    await run(session, scriptedIo("exit", "quit"));

    expect(session.questions).toEqual(["exit", "quit"]);
  });

  it("skips blank lines", async () => {
    const session = new FakeSession();

    await run(session, scriptedIo("", "  ", "hi"));

    expect(session.questions).toEqual(["hi"]);
  });

  it("closes the input when it is done", async () => {
    const io = scriptedIo("hi");

    await run(new FakeSession(), io);

    expect(io.closed).toBe(true);
  });

  it("closes the input even when the session throws", async () => {
    const io = scriptedIo("hi");
    const session: Session = {
      async ask() {
        throw new Error("boom");
      },
    };

    await expect(run(session, io)).rejects.toThrow("boom");
    expect(io.closed).toBe(true);
  });
});

describe("ChatSession", () => {
  it("returns the model's reply", async () => {
    const client = new FakeLlmClient();
    client.reply = "hello there";

    const answer = await startSession(buildChatGraph(client)).ask("hi");

    expect(answer).toBe("hello there");
  });

  it("keeps the history across questions", async () => {
    const client = new FakeLlmClient();
    const session = startSession(buildChatGraph(client));

    await session.ask("first");
    await session.ask("second");

    expect(contentsOf(client.lastCall)).toEqual(
      expect.arrayContaining(["first", "second"]),
    );
  });

  it("does not accumulate the system prompt", async () => {
    const client = new FakeLlmClient();
    const session = startSession(buildChatGraph(client));

    await session.ask("first");
    await session.ask("second");

    expect(
      client.lastCall.filter((message) => message instanceof SystemMessage),
    ).toHaveLength(1);
  });

  it("gives two sessions independent history", async () => {
    const client = new FakeLlmClient();
    const a = startSession(buildChatGraph(client));
    const b = startSession(buildChatGraph(client));

    await a.ask("from a");
    await b.ask("from b");

    expect(contentsOf(client.lastCall)).toContain("from b");
    expect(contentsOf(client.lastCall)).not.toContain("from a");
  });

  it("gives each session its own thread id", () => {
    const client = new FakeLlmClient();
    const graph = buildChatGraph(client);

    expect(startSession(graph).threadId).not.toBe(startSession(graph).threadId);
  });
});
