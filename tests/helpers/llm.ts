import type { BaseMessage } from "@langchain/core/messages";
import type { LlmClient, ModelReply, NamedSchema } from "../../src/clients/llm.js";
import { aiMessage } from "./model.js";

export class FakeLlmClient implements LlmClient {
  reply = "fake reply";
  structuredReply: unknown;
  readonly calls: BaseMessage[][] = [];
  failStructuredCall: number | undefined;
  private structuredCalls = 0;

  async complete(messages: readonly BaseMessage[]): Promise<ModelReply> {
    this.calls.push([...messages]);
    return aiMessage(this.reply);
  }

  async completeStructured<T>(
    messages: readonly BaseMessage[],
    schema: NamedSchema<T>,
  ): Promise<T> {
    this.calls.push([...messages]);
    this.structuredCalls += 1;
    if (this.structuredCalls === this.failStructuredCall) {
      throw new Error("llm exploded");
    }
    if (this.structuredReply !== undefined) {
      return schema.schema.parse(this.structuredReply);
    }
    return schema.schema.parse({
      summary: "fake summary",
      findings: [{ severity: "minor", title: "fake finding", detail: "fake detail" }],
    });
  }

  get lastCall(): BaseMessage[] {
    const call = this.calls.at(-1);
    if (call === undefined) {
      throw new Error("the model was never called");
    }
    return call;
  }
}

export function contentsOf(messages: readonly BaseMessage[]): string[] {
  return messages.map((message) =>
    typeof message.content === "string" ? message.content : "",
  );
}
