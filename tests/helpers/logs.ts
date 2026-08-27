import { readFileSync } from "node:fs";
import { afterEach, beforeEach } from "vitest";
import {
  type LogContext,
  type LogRecord,
  resetHandlers,
  setHandlers,
} from "../../packages/shared/logs.js";

export function readJsonLines(path: string): Record<string, unknown>[] {
  return readFileSync(path, "utf8")
    .split("\n")
    .filter((line) => line.trim() !== "")
    .map((line) => JSON.parse(line) as Record<string, unknown>);
}

export class LogCapture {
  readonly records: LogRecord[] = [];

  withMessage(message: string): LogRecord[] {
    return this.records.filter((record) => record.message === message);
  }

  contextOf(message: string): LogContext {
    const record = this.withMessage(message)[0];
    if (record === undefined) {
      throw new Error(`no log record with message ${JSON.stringify(message)}`);
    }
    return record.context;
  }
}

export function useLogCapture(): LogCapture {
  const capture = new LogCapture();

  beforeEach(() => {
    capture.records.length = 0;
    setHandlers([{ handle: (record) => capture.records.push(record) }]);
  });

  afterEach(() => {
    resetHandlers();
  });

  return capture;
}
