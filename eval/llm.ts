import type { BaseMessage } from "@langchain/core/messages";
import type { LlmClient, ModelReply, NamedSchema } from "../apps/server/index.js";

interface StructuredCall {
  readonly schema: string;
  readonly output: unknown;
}

export class RecordingLlmClient implements LlmClient {
  private readonly structuredCalls: StructuredCall[] = [];

  constructor(private readonly inner: LlmClient) {}

  complete(messages: readonly BaseMessage[]): Promise<ModelReply> {
    return this.inner.complete(messages);
  }

  async completeStructured<T>(
    messages: readonly BaseMessage[],
    schema: NamedSchema<T>,
  ): Promise<T> {
    const output = await this.inner.completeStructured(messages, schema);
    this.structuredCalls.push({ schema: schema.name, output });
    return output;
  }

  outputsFor<T>(schema: NamedSchema<T>): T[] {
    return this.structuredCalls
      .filter((call) => call.schema === schema.name)
      .map((call) => schema.schema.parse(call.output));
  }
}
