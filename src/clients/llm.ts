import type {
  AIMessage,
  BaseMessage,
  StandardMessageStructure,
} from "@langchain/core/messages";
import { ChatOpenAI } from "@langchain/openai";
import { z } from "zod";
import { loadEnvVar } from "../env.js";
import { getLogger } from "../logs.js";

const log = getLogger("angel.clients.llm");

/** A zod schema paired with the name the provider sees in `response_format`. */
export interface NamedSchema<T> {
  readonly name: string;
  readonly schema: z.ZodType<T>;
}

/** Pairs a schema with the name it is requested under. */
export function namedSchema<T>(name: string, schema: z.ZodType<T>): NamedSchema<T> {
  return { name, schema };
}

/** The seam every agent talks to the model through. */
export interface LlmClient {
  complete(messages: readonly BaseMessage[]): Promise<ModelReply>;
  completeStructured<T>(
    messages: readonly BaseMessage[],
    schema: NamedSchema<T>,
  ): Promise<T>;
}

/** A reply from the model, with the metadata the standard structure carries. */
export type ModelReply = AIMessage<StandardMessageStructure>;

/** The provider arguments this client sets per call. */
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

/** The part of a chat model this client drives. */
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

/** A snapshot of the run's model spend; later calls do not mutate it. */
export function usageTotals(): UsageTotals {
  return { ...totals };
}

/** Zeroes the run tally. `main` calls this once before the command runs. */
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

export const NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1";
export const NVIDIA_MODEL = "nvidia/nemotron-3-ultra-550b-a55b";
export const NVIDIA_MAX_COMPLETION_TOKENS_DEFAULT = 32768;
export const NVIDIA_TIMEOUT_MS = 300_000;
export const NVIDIA_TEMPERATURE = 0;

/**
 * Talks to an NVIDIA-hosted, OpenAI-compatible endpoint.
 *
 * Structured replies go through the provider's `json_schema` response format
 * and are validated here rather than through LangChain's `withStructuredOutput`,
 * whose fallback chain retries a truncated reply with a `guided_json` field the
 * endpoint rejects — turning a truncation into a misleading 400.
 */
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

/** Builds the configured client, or throws naming the variable at fault. */
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
