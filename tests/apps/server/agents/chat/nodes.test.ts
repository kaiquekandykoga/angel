import { AIMessage, HumanMessage, SystemMessage } from "@langchain/core/messages";
import { describe, expect, it } from "vitest";
import { callLlm } from "../../../../../apps/server/agents/chat/nodes.js";
import { SYSTEM_PROMPT } from "../../../../../apps/server/agents/chat/prompts.js";
import { FakeLlmClient } from "../../../../helpers/llm.js";
import { useLogCapture } from "../../../../helpers/logs.js";

describe("callLlm", () => {
  const logs = useLogCapture();

  it("appends the model's reply", async () => {
    const client = new FakeLlmClient();

    const result = await callLlm(client)({ messages: [new HumanMessage("hi")] });

    expect(result.messages.at(-1)).toBeInstanceOf(AIMessage);
    expect(result.messages.at(-1)?.content).toBe(client.reply);
  });

  it("prepends the system prompt without persisting it", async () => {
    const client = new FakeLlmClient();

    const result = await callLlm(client)({ messages: [new HumanMessage("hi")] });

    expect(client.lastCall[0]).toBeInstanceOf(SystemMessage);
    expect(client.lastCall[0]?.content).toBe(SYSTEM_PROMPT);
    expect(result.messages.some((message) => message instanceof SystemMessage)).toBe(
      false,
    );
  });

  it("logs the message count in and the reply length out, at debug", async () => {
    const client = new FakeLlmClient();

    await callLlm(client)({ messages: [new HumanMessage("hi")] });

    expect(logs.records.every((record) => record.level === "DEBUG")).toBe(true);
    expect(logs.contextOf("call_llm completed")).toEqual({
      message_count: 2,
      reply_length: client.reply.length,
    });
  });
});
