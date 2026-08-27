import {
  AIMessage,
  HumanMessage,
  type StandardMessageStructure,
} from "@langchain/core/messages";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { z } from "zod";
import {
  buildLlmClient,
  InvalidMaxCompletionTokensError,
  MissingApiKeyError,
  NvidiaClient,
  namedSchema,
  resetUsage,
  TruncatedCompletionError,
  usageTotals,
} from "../../../src/clients/llm.js";
import { resetEnvCache } from "../../../src/env.js";
import { configureLogging, resetHandlers } from "../../../src/logs.js";
import { readJsonLines } from "../../helpers/logs.js";
import { aiMessage, FakeChatModel } from "../../helpers/model.js";
import { MemoryStream } from "../../helpers/stream.js";
import { useTemporaryDirectory } from "../../helpers/tmp.js";

const REVIEW = namedSchema(
  "Review",
  z.object({ summary: z.string(), score: z.number() }),
);

describe("NvidiaClient.complete", () => {
  beforeEach(() => {
    resetUsage();
  });

  it("passes the messages through and returns the reply", async () => {
    const model = new FakeChatModel(aiMessage("hello there"));
    const client = new NvidiaClient(model, 1024);

    const reply = await client.complete([new HumanMessage("hi")]);

    expect(reply.content).toBe("hello there");
    expect(model.received[0]).toHaveLength(1);
  });

  it("counts the call in the usage totals even without usage metadata", async () => {
    const client = new NvidiaClient(new FakeChatModel(aiMessage("hi")), 1024);

    await client.complete([new HumanMessage("hi")]);

    const totals = usageTotals();
    expect(totals.calls).toBe(1);
    expect(totals.totalTokens).toBe(0);
    expect(totals.durationMs).toBeGreaterThanOrEqual(0);
  });

  it("accumulates token counts across calls", async () => {
    const model = new FakeChatModel(
      aiMessage("hi", { usage: { input: 10, output: 5, total: 15 } }),
    );
    const client = new NvidiaClient(model, 1024);

    await client.complete([new HumanMessage("a")]);
    await client.complete([new HumanMessage("b")]);

    expect(usageTotals()).toMatchObject({
      calls: 2,
      inputTokens: 20,
      outputTokens: 10,
      totalTokens: 30,
    });
  });

  it("hands back a snapshot that later calls do not mutate", async () => {
    const client = new NvidiaClient(
      new FakeChatModel(aiMessage("hi", { usage: { input: 1, output: 1, total: 2 } })),
      1024,
    );

    await client.complete([new HumanMessage("a")]);
    const snapshot = usageTotals();
    await client.complete([new HumanMessage("b")]);

    expect(snapshot.calls).toBe(1);
    expect(usageTotals().calls).toBe(2);
  });

  it("is zeroed by resetUsage", async () => {
    const client = new NvidiaClient(new FakeChatModel(aiMessage("hi")), 1024);
    await client.complete([new HumanMessage("a")]);

    resetUsage();

    expect(usageTotals()).toMatchObject({ calls: 0, totalTokens: 0, durationMs: 0 });
  });
});

describe("NvidiaClient.completeStructured", () => {
  beforeEach(() => {
    resetUsage();
  });

  it("binds a strict json_schema response format named after the schema", async () => {
    const model = new FakeChatModel(
      aiMessage(JSON.stringify({ summary: "ok", score: 1 })),
    );

    await new NvidiaClient(model, 1024).completeStructured(
      [new HumanMessage("review this")],
      REVIEW,
    );

    expect(model.lastOptions).toMatchObject({
      response_format: {
        type: "json_schema",
        json_schema: { name: "Review", strict: true },
      },
    });
  });

  it("validates the reply against the schema", async () => {
    const model = new FakeChatModel(
      aiMessage(JSON.stringify({ summary: "ok", score: 3 })),
    );

    const output = await new NvidiaClient(model, 1024).completeStructured(
      [new HumanMessage("review")],
      REVIEW,
    );

    expect(output).toEqual({ summary: "ok", score: 3 });
  });

  it("rejects a reply that does not fit the schema", async () => {
    const model = new FakeChatModel(aiMessage(JSON.stringify({ summary: "ok" })));

    await expect(
      new NvidiaClient(model, 1024).completeStructured([new HumanMessage("x")], REVIEW),
    ).rejects.toThrow();
  });

  it("rejects a reply that is not JSON at all", async () => {
    const model = new FakeChatModel(aiMessage("not json"));

    await expect(
      new NvidiaClient(model, 1024).completeStructured([new HumanMessage("x")], REVIEW),
    ).rejects.toThrow();
  });

  it("raises TruncatedCompletionError when the reply hit the ceiling", async () => {
    const model = new FakeChatModel(
      aiMessage('{"summary": "ok"', {
        finishReason: "length",
        usage: { input: 100, output: 900, total: 1000 },
      }),
    );

    await expect(
      new NvidiaClient(model, 1024).completeStructured([new HumanMessage("x")], REVIEW),
    ).rejects.toThrow(TruncatedCompletionError);
  });

  it("names the schema, the ceiling and the usage in the truncation message", async () => {
    const model = new FakeChatModel(
      aiMessage("{", {
        finishReason: "length",
        usage: { input: 100, output: 900, total: 1000 },
      }),
    );

    await expect(
      new NvidiaClient(model, 1024).completeStructured([new HumanMessage("x")], REVIEW),
    ).rejects.toThrow(
      /Review.*truncated.*1024.*input_tokens=100, output_tokens=900, total_tokens=1000/s,
    );
  });

  it("says so when a truncated reply carries no usage metadata", async () => {
    const model = new FakeChatModel(aiMessage("{", { finishReason: "length" }));

    await expect(
      new NvidiaClient(model, 1024).completeStructured([new HumanMessage("x")], REVIEW),
    ).rejects.toThrow(/usage metadata unavailable/);
  });

  it("rejects non-string content", async () => {
    const model = new FakeChatModel(
      new AIMessage<StandardMessageStructure>({
        content: [{ type: "text", text: "{}" }],
        response_metadata: { finish_reason: "stop" },
      }),
    );

    await expect(
      new NvidiaClient(model, 1024).completeStructured([new HumanMessage("x")], REVIEW),
    ).rejects.toThrow(/Expected string content/);
  });

  it("still counts a truncated call in the usage totals", async () => {
    const model = new FakeChatModel(
      aiMessage("{", {
        finishReason: "length",
        usage: { input: 1, output: 2, total: 3 },
      }),
    );

    await expect(
      new NvidiaClient(model, 1024).completeStructured([new HumanMessage("x")], REVIEW),
    ).rejects.toThrow(TruncatedCompletionError);
    expect(usageTotals()).toMatchObject({ calls: 1, totalTokens: 3 });
  });
});

describe("model call logging", () => {
  const temporary = useTemporaryDirectory();

  beforeEach(() => {
    resetUsage();
  });

  afterEach(() => {
    resetHandlers();
  });

  it("logs one record per call with the fields the docs promise", async () => {
    const path = configureLogging({
      directory: temporary.path,
      stream: new MemoryStream(),
    });
    const model = new FakeChatModel(
      aiMessage(JSON.stringify({ summary: "ok", score: 1 }), {
        usage: { input: 7, output: 3, total: 10 },
      }),
    );

    await new NvidiaClient(model, 1024).completeStructured(
      [new HumanMessage("x")],
      REVIEW,
    );

    const record = readJsonLines(path).find(
      (entry) => entry.message === "model call completed",
    );
    expect(record).toMatchObject({
      level: "DEBUG",
      call: "complete_structured",
      schema: "Review",
      finish_reason: "stop",
      input_tokens: 7,
      output_tokens: 3,
      total_tokens: 10,
    });
    expect(record?.duration_ms).toEqual(expect.any(Number));
  });

  it("omits the schema key for a plain completion and nulls absent usage", async () => {
    const path = configureLogging({
      directory: temporary.path,
      stream: new MemoryStream(),
    });

    await new NvidiaClient(new FakeChatModel(aiMessage("hi")), 1024).complete([
      new HumanMessage("x"),
    ]);

    const record = readJsonLines(path).find(
      (entry) => entry.message === "model call completed",
    );
    expect(record).toMatchObject({ call: "complete", input_tokens: null });
    expect(record).not.toHaveProperty("schema");
  });
});

describe("buildLlmClient", () => {
  beforeEach(() => {
    resetEnvCache();
    delete process.env.ANGEL_NVIDIA_API_KEY;
    delete process.env.ANGEL_NVIDIA_MAX_COMPLETION_TOKENS;
  });

  it("raises when the API key is missing", () => {
    expect(() => buildLlmClient()).toThrow(MissingApiKeyError);
    expect(() => buildLlmClient()).toThrow(
      "ANGEL_NVIDIA_API_KEY environment variable is not set.",
    );
  });

  it("builds a client when only the API key is set", () => {
    process.env.ANGEL_NVIDIA_API_KEY = "key";
    expect(buildLlmClient()).toBeInstanceOf(NvidiaClient);
  });

  it.each(["not-a-number", "4.5", "0", "-1", " "])(
    "rejects %s as a token ceiling",
    (value) => {
      process.env.ANGEL_NVIDIA_API_KEY = "key";
      process.env.ANGEL_NVIDIA_MAX_COMPLETION_TOKENS = value;

      expect(() => buildLlmClient()).toThrow(InvalidMaxCompletionTokensError);
    },
  );

  it("accepts a positive integer ceiling", () => {
    process.env.ANGEL_NVIDIA_API_KEY = "key";
    process.env.ANGEL_NVIDIA_MAX_COMPLETION_TOKENS = "4096";

    expect(buildLlmClient().maxCompletionTokens).toBe(4096);
  });

  it("falls back to the default ceiling when the variable is empty", () => {
    process.env.ANGEL_NVIDIA_API_KEY = "key";
    process.env.ANGEL_NVIDIA_MAX_COMPLETION_TOKENS = "";

    expect(buildLlmClient().maxCompletionTokens).toBe(32768);
  });
});
