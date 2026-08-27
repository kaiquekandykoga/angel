import { appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import {
  BOLD,
  CYAN,
  colorEnabled,
  DIM,
  type OutputStream,
  RED,
  style,
  YELLOW,
} from "./console.js";

export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

export type LogContext = Readonly<Record<string, unknown>>;

export interface LogRecord {
  readonly time: string;
  readonly level: LogLevel;
  readonly logger: string;
  readonly message: string;
  readonly context: LogContext;
}

export interface LogHandler {
  handle(record: LogRecord): void;
}

const LEVEL_ORDER: Record<LogLevel, number> = {
  DEBUG: 10,
  INFO: 20,
  WARNING: 30,
  ERROR: 40,
  CRITICAL: 50,
};

const LEVEL_CODES: Record<LogLevel, readonly string[]> = {
  DEBUG: [DIM],
  INFO: [CYAN],
  WARNING: [YELLOW],
  ERROR: [RED],
  CRITICAL: [BOLD, RED],
};

/** Renders a record the way the console handler does: `LEVEL   message`. */
export function formatConsoleRecord(record: LogRecord, stream: OutputStream): string {
  const padded = record.level.padEnd(7);
  const levelName = colorEnabled(stream)
    ? style(padded, LEVEL_CODES[record.level], stream)
    : padded;
  return `${levelName} ${record.message}`;
}

class ConsoleHandler implements LogHandler {
  constructor(
    private readonly stream: OutputStream,
    private readonly minimumLevel: LogLevel,
  ) {}

  handle(record: LogRecord): void {
    if (LEVEL_ORDER[record.level] < LEVEL_ORDER[this.minimumLevel]) {
      return;
    }
    this.stream.write(`${formatConsoleRecord(record, this.stream)}\n`);
  }
}

class JsonLinesHandler implements LogHandler {
  constructor(private readonly path: string) {}

  handle(record: LogRecord): void {
    const payload = {
      time: record.time,
      level: record.level,
      logger: record.logger,
      message: record.message,
      ...record.context,
    };
    appendFileSync(this.path, `${JSON.stringify(payload)}\n`);
  }
}

let handlers: LogHandler[] = [];

/** Replaces the installed handlers. Test seam. */
export function setHandlers(next: readonly LogHandler[]): void {
  handlers = [...next];
}

/** Removes every handler, so records are dropped. Test seam. */
export function resetHandlers(): void {
  handlers = [];
}

function stamp(timestamp: Date): string {
  return `${timestamp.toISOString().slice(0, 19).replace(/[-:]/g, "")}Z`;
}

export interface LoggingOptions {
  readonly directory?: string;
  readonly timestamp?: Date;
  readonly stream?: OutputStream;
}

/**
 * Sends `DEBUG` and above to `<directory>/angel-<timestamp>.jsonl` and `INFO`
 * and above to the console, and returns the file path.
 */
export function configureLogging(options: LoggingOptions = {}): string {
  const directory = options.directory ?? "log";
  const timestamp = options.timestamp ?? new Date();
  const stream = options.stream ?? process.stderr;

  mkdirSync(directory, { recursive: true });
  const path = join(directory, `angel-${stamp(timestamp)}.jsonl`);

  setHandlers([new ConsoleHandler(stream, "INFO"), new JsonLinesHandler(path)]);
  return path;
}

/** A logger that takes structured fields alongside the message. */
export class ContextLogger {
  constructor(readonly name: string) {}

  private emit(level: LogLevel, message: string, context: LogContext): void {
    const record: LogRecord = {
      time: new Date().toISOString(),
      level,
      logger: this.name,
      message,
      context,
    };
    for (const handler of handlers) {
      handler.handle(record);
    }
  }

  debug(message: string, context: LogContext = {}): void {
    this.emit("DEBUG", message, context);
  }

  info(message: string, context: LogContext = {}): void {
    this.emit("INFO", message, context);
  }

  warning(message: string, context: LogContext = {}): void {
    this.emit("WARNING", message, context);
  }

  error(message: string, context: LogContext = {}): void {
    this.emit("ERROR", message, context);
  }
}

/** Returns the logger named for the calling module. */
export function getLogger(name: string): ContextLogger {
  return new ContextLogger(name);
}
