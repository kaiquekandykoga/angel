import type {
  AIMessage,
  BaseMessage,
  StandardMessageStructure,
} from "@langchain/core/messages";
import { ChatOpenAI } from "@langchain/openai";
import { z } from "zod";
import { loadEnvVar } from "../../../../packages/shared/env.js";
import { getLogger } from "../../../../packages/shared/logs.js";
import {
  NVIDIA_BASE_URL,
  NVIDIA_MAX_COMPLETION_TOKENS_DEFAULT,
  NVIDIA_MODEL,
  NVIDIA_TEMPERATURE,
  NVIDIA_TIMEOUT_MS,
} from "./settings.js";

const log = getLogger("angel.external.nvidia");

export interface NamedSchema<T> {
  readonly name: string;
  readonly schema: z.ZodType<T>;
}

export function namedSchema<T>(name: string, schema: z.ZodType<T>): NamedSchema<T> {
  return { name, schema };
}

export interface LlmClient {
  complete(messages: readonly BaseMessage[]): Promise<ModelReply>;
  completeStructured<T>(
    messages: readonly BaseMessage[],
    schema: NamedSchema<T>,
  ): Promise<T>;
}

export type ModelReply = AIMessage<StandardMessageStructure>;

export interface ModelCallOptions {
  readonly response_format?: {
    readonly type: "json_schema";
    readonly json_schema: {
      readonly name: string;
      readonly schema: Record<string, unknown>;
      readonly strict: true;
    };
  };
}

export interface ChatModel {
  invoke(messages: BaseMessage[], options?: ModelCallOptions): Promise<ModelReply>;
}

export class MissingApiKeyError extends Error {
  override readonly name = "MissingApiKeyError";
}

export class InvalidMaxCompletionTokensError extends Error {
  override readonly name = "InvalidMaxCompletionTokensError";
}

export class TruncatedCompletionError extends Error {
  override readonly name = "TruncatedCompletionError";
}

export interface UsageTotals {
  readonly calls: number;
  readonly inputTokens: number;
  readonly outputTokens: number;
  readonly totalTokens: number;
  readonly durationMs: number;
}

const ZERO_USAGE: UsageTotals = {
  calls: 0,
  inputTokens: 0,
  outputTokens: 0,
  totalTokens: 0,
  durationMs: 0,
};

let totals: UsageTotals = ZERO_USAGE;

export function usageTotals(): UsageTotals {
  return { ...totals };
}

export function resetUsage(): void {
  totals = ZERO_USAGE;
}

function logModelCallCompleted(
  startedAt: number,
  options: { call: string; reply: ModelReply; schema?: string },
): void {
  const usage = options.reply.usage_metadata;
  const durationMs = Math.round((performance.now() - startedAt) * 10) / 10;
  const context: Record<string, unknown> = { call: options.call };
  if (options.schema !== undefined) {
    context.schema = options.schema;
  }
  context.finish_reason = options.reply.response_metadata.finish_reason ?? null;
  context.input_tokens = usage?.input_tokens ?? null;
  context.output_tokens = usage?.output_tokens ?? null;
  context.total_tokens = usage?.total_tokens ?? null;
  context.duration_ms = durationMs;
  log.debug("model call completed", context);

  totals = {
    calls: totals.calls + 1,
    inputTokens: totals.inputTokens + (usage?.input_tokens ?? 0),
    outputTokens: totals.outputTokens + (usage?.output_tokens ?? 0),
    totalTokens: totals.totalTokens + (usage?.total_tokens ?? 0),
    durationMs: totals.durationMs + durationMs,
  };
}

export class NvidiaClient implements LlmClient {
  constructor(
    private readonly chatModel: ChatModel,
    readonly maxCompletionTokens: number,
  ) {}

  async complete(messages: readonly BaseMessage[]): Promise<ModelReply> {
    const startedAt = performance.now();
    const reply = await this.chatModel.invoke([...messages]);
    logModelCallCompleted(startedAt, { call: "complete", reply });
    return reply;
  }

  async completeStructured<T>(
    messages: readonly BaseMessage[],
    schema: NamedSchema<T>,
  ): Promise<T> {
    const startedAt = performance.now();
    const reply = await this.chatModel.invoke([...messages], {
      response_format: {
        type: "json_schema",
        json_schema: {
          name: schema.name,
          schema: z.toJSONSchema(schema.schema, { io: "input" }),
          strict: true,
        },
      },
    });
    logModelCallCompleted(startedAt, {
      call: "complete_structured",
      reply,
      schema: schema.name,
    });

    if (reply.response_metadata.finish_reason === "length") {
      const usage = reply.usage_metadata;
      const usageText = usage
        ? `input_tokens=${usage.input_tokens}, ` +
          `output_tokens=${usage.output_tokens}, ` +
          `total_tokens=${usage.total_tokens}`
        : "usage metadata unavailable";
      throw new TruncatedCompletionError(
        `Completion for schema "${schema.name}" was truncated: the model hit ` +
          `the max_completion_tokens limit of ${this.maxCompletionTokens} ` +
          `(${usageText}).`,
      );
    }
    if (typeof reply.content !== "string") {
      throw new TypeError(
        `Expected string content for schema "${schema.name}", got ` +
          `${typeof reply.content} instead.`,
      );
    }
    return schema.schema.parse(JSON.parse(reply.content));
  }
}

function readMaxCompletionTokens(): number {
  const raw = loadEnvVar("ANGEL_NVIDIA_MAX_COMPLETION_TOKENS");
  if (raw === undefined || raw === "") {
    return NVIDIA_MAX_COMPLETION_TOKENS_DEFAULT;
  }
  const parsed = /^\s*[+-]?\d+\s*$/.test(raw) ? Number(raw) : Number.NaN;
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    throw new InvalidMaxCompletionTokensError(
      "ANGEL_NVIDIA_MAX_COMPLETION_TOKENS must be a positive integer, got " +
        `${JSON.stringify(raw)}.`,
    );
  }
  return parsed;
}

export function buildLlmClient(): NvidiaClient {
  const apiKey = loadEnvVar("ANGEL_NVIDIA_API_KEY");
  if (!apiKey) {
    throw new MissingApiKeyError(
      "ANGEL_NVIDIA_API_KEY environment variable is not set.",
    );
  }
  const maxCompletionTokens = readMaxCompletionTokens();

  const chatModel = new ChatOpenAI({
    apiKey,
    configuration: { baseURL: NVIDIA_BASE_URL },
    model: NVIDIA_MODEL,
    maxCompletionTokens,
    timeout: NVIDIA_TIMEOUT_MS,
    temperature: NVIDIA_TEMPERATURE,
  });
  return new NvidiaClient(chatModel, maxCompletionTokens);
}
