import { AIMessage, HumanMessage } from "@langchain/core/messages";
import { describe, expect, it } from "vitest";
import { buildChatGraph } from "../../../../../apps/server/agents/chat/graph.js";
import { FakeLlmClient } from "../../../../helpers/llm.js";
import { useLogCapture } from "../../../../helpers/logs.js";

describe("buildChatGraph", () => {
  const logs = useLogCapture();

  it("routes through the chat node", async () => {
    const client = new FakeLlmClient();
    const graph = buildChatGraph(client);

    const result = await graph.invoke(
      { messages: [new HumanMessage("hi")] },
      { configurable: { thread_id: "t1" } },
    );

    expect(result.messages.at(-1)).toBeInstanceOf(AIMessage);
    expect(result.messages.at(-1)?.content).toBe(client.reply);
  });

  it("logs the wiring and that the graph is ready", () => {
    buildChatGraph(new FakeLlmClient());

    expect(logs.records.map((record) => record.level)).toEqual(
      expect.arrayContaining(["DEBUG", "INFO"]),
    );
  });
});
