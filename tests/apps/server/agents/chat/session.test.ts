import { SystemMessage } from "@langchain/core/messages";
import { describe, expect, it } from "vitest";
import { buildChatGraph } from "../../../../../apps/server/agents/chat/graph.js";
import { startSession } from "../../../../../apps/server/agents/chat/session.js";
import { contentsOf, FakeLlmClient } from "../../../../helpers/llm.js";

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
