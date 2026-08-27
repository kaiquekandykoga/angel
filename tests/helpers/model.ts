import {
  AIMessage,
  type BaseMessage,
  type StandardMessageStructure,
} from "@langchain/core/messages";
import type { ChatModel, ModelCallOptions, ModelReply } from "../../src/clients/llm.js";

export interface FakeReplyOptions {
  readonly finishReason?: string | null;
  readonly usage?: { input: number; output: number; total: number };
  readonly content?: unknown;
}

/** Builds an AI reply carrying the metadata the client reads. */
export function aiMessage(content: string, options: FakeReplyOptions = {}): ModelReply {
  return new AIMessage<StandardMessageStructure>({
    content,
    response_metadata: { finish_reason: options.finishReason ?? "stop" },
    ...(options.usage
      ? {
          usage_metadata: {
            input_tokens: options.usage.input,
            output_tokens: options.usage.output,
            total_tokens: options.usage.total,
          },
        }
      : {}),
  });
}

/** A chat model that always replies the same way and records what it saw. */
export class FakeChatModel implements ChatModel {
  lastOptions: ModelCallOptions | undefined;
  received: BaseMessage[][] = [];

  constructor(private readonly reply: ModelReply) {}

  async invoke(
    messages: BaseMessage[],
    options?: ModelCallOptions,
  ): Promise<ModelReply> {
    this.received.push(messages);
    this.lastOptions = options;
    return this.reply;
  }
}
