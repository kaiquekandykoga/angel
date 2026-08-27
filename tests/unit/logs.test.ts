import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { CYAN, RED, YELLOW } from "../../src/console.js";
import { resetEnvCache } from "../../src/env.js";
import {
  configureLogging,
  formatConsoleRecord,
  getLogger,
  type LogLevel,
  resetHandlers,
} from "../../src/logs.js";
import { stripAnsi } from "../helpers/ansi.js";
import { MemoryStream } from "../helpers/stream.js";
import { useTemporaryDirectory } from "../helpers/tmp.js";

function readRecords(path: string): Record<string, unknown>[] {
  return readFileSync(path, "utf8")
    .trim()
    .split("\n")
    .filter((line) => line !== "")
    .map((line) => JSON.parse(line) as Record<string, unknown>);
}

describe("configureLogging", () => {
  const temporary = useTemporaryDirectory();

  afterEach(() => {
    resetHandlers();
  });

  it("creates the directory and returns a timestamped path", () => {
    const directory = join(temporary.path, "log");
    const timestamp = new Date(Date.UTC(2026, 7, 7, 12, 30, 45));

    const path = configureLogging({ directory, timestamp });

    expect(existsSync(directory)).toBe(true);
    expect(path).toBe(join(directory, "angel-20260807T123045Z.jsonl"));
  });

  it("writes one JSON object per line with the context merged in", () => {
    const path = configureLogging({ directory: temporary.path });

    getLogger("angel").info("hello", { foo: "bar" });

    const [record] = readRecords(path);
    expect(record).toMatchObject({
      level: "INFO",
      logger: "angel",
      message: "hello",
      foo: "bar",
    });
    expect(record?.time).toEqual(expect.any(String));
  });

  it("keeps DEBUG out of the console but writes it to the file", () => {
    const stream = new MemoryStream();
    const path = configureLogging({ directory: temporary.path, stream });

    getLogger("angel").debug("quiet");
    getLogger("angel").info("loud");

    expect(stream.text).not.toContain("quiet");
    expect(stream.text).toContain("loud");
    expect(readRecords(path).map((record) => record.message)).toEqual([
      "quiet",
      "loud",
    ]);
  });

  it("replaces the handlers rather than stacking them when called twice", () => {
    configureLogging({ directory: temporary.path });
    const path = configureLogging({ directory: temporary.path });

    getLogger("angel").info("once");

    expect(readRecords(path)).toHaveLength(1);
  });

  it("drops records when logging has not been configured", () => {
    resetHandlers();
    expect(() => getLogger("angel").info("nowhere")).not.toThrow();
  });
});

describe("getLogger", () => {
  const temporary = useTemporaryDirectory();

  afterEach(() => {
    resetHandlers();
  });

  it.each([
    ["debug", "DEBUG"],
    ["info", "INFO"],
    ["warning", "WARNING"],
    ["error", "ERROR"],
  ] as const)("maps %s to level %s", (method, level) => {
    const path = configureLogging({ directory: temporary.path });

    getLogger("angel")[method]("message", { key: "value" });

    expect(readRecords(path)[0]).toMatchObject({ level, key: "value" });
  });

  it("names the record after the module that emitted it", () => {
    const path = configureLogging({ directory: temporary.path });

    getLogger("angel.agents.pr-review.nodes").debug("evaluated pull request", {
      number: 7,
    });

    expect(readRecords(path)[0]).toMatchObject({
      logger: "angel.agents.pr-review.nodes",
      message: "evaluated pull request",
      number: 7,
    });
  });

  it("produces a valid record when there are no context fields", () => {
    const path = configureLogging({ directory: temporary.path });

    getLogger("angel").info("no fields here");

    const [record] = readRecords(path);
    expect(record).toMatchObject({
      level: "INFO",
      logger: "angel",
      message: "no fields here",
    });
    expect(record?.time).toEqual(expect.any(String));
  });

  it("writes an ISO-8601 UTC timestamp", () => {
    const path = configureLogging({ directory: temporary.path });

    getLogger("angel").info("stamped");

    expect(readRecords(path)[0]?.time).toMatch(
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/,
    );
  });
});

describe("formatConsoleRecord", () => {
  beforeEach(() => {
    resetEnvCache();
    delete process.env.NO_COLOR;
    delete process.env.ANGEL_COLOR;
  });

  const record = (level: LogLevel, message: string) => ({
    time: "2026-08-07T12:30:45.000Z",
    level,
    logger: "angel",
    message,
    context: {},
  });

  it("pads the level name and leaves the message plain when color is off", () => {
    process.env.ANGEL_COLOR = "never";
    const text = formatConsoleRecord(record("INFO", "hello"), new MemoryStream());

    expect(text).toBe("INFO    hello");
  });

  it("colors the level name only", () => {
    process.env.ANGEL_COLOR = "always";
    const text = formatConsoleRecord(record("INFO", "hello"), new MemoryStream());

    expect(text).toContain(`\x1b[${CYAN}mINFO   \x1b[0m`);
    expect(stripAnsi(text)).toBe("INFO    hello");
  });

  it.each([
    ["WARNING", YELLOW],
    ["ERROR", RED],
  ] as const)("maps %s to its color", (level, code) => {
    process.env.ANGEL_COLOR = "always";
    const text = formatConsoleRecord(record(level, "message"), new MemoryStream());

    expect(text).toContain(`\x1b[${code}m${level.padEnd(7)}\x1b[0m`);
  });
});
