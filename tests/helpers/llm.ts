import type { BaseMessage } from "@langchain/core/messages";
import type { LlmClient, ModelReply, NamedSchema } from "../../src/clients/llm.js";
import { aiMessage } from "./model.js";

/** A model that replies from a script instead of the network. */
export class FakeLlmClient implements LlmClient {
  reply = "fake reply";
  /** When set, every structured call returns this instead of the default shape. */
  structuredReply: unknown;
  /** Every batch of messages the client was asked to complete. */
  readonly calls: BaseMessage[][] = [];
  /** Set to fail the nth structured call, counting from 1. */
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

/** The text of every message in a batch, for order-insensitive assertions. */
export function contentsOf(messages: readonly BaseMessage[]): string[] {
  return messages.map((message) =>
    typeof message.content === "string" ? message.content : "",
  );
}
