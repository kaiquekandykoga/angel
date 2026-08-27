import { CommanderError, Command as Program } from "commander";
import type { ItemFailure, Review } from "./agents/shared.js";
import type { UsageTotals } from "./clients/llm.js";
import { BOLD, DIM, GREEN, type OutputStream, RED, section, style } from "./console.js";

export class ExitError extends Error {
  override readonly name = "ExitError";

  constructor(
    readonly code: number,
    message = "",
  ) {
    super(message);
  }
}

export const COMMANDS = ["chat", "pr_review", "issue_review"] as const;

export type Command = (typeof COMMANDS)[number];

export const DRY_RUN_HELP = "Print each review to stdout and make zero GitHub writes";

const PROGRAM_DESCRIPTION =
  "Chat with the model, or review labeled pull requests and issues.";

const HELP_FLAGS_HELP = "show this help message and exit";

const DESCRIPTIONS: Record<Command, string> = {
  chat: "Start an interactive chat session with the model.",
  pr_review: "Review open pull requests labeled angel.",
  issue_review: "Review open issues labeled angel.",
};

const SUMMARIES: Record<Command, string> = {
  chat: "Interactive REPL against the model",
  pr_review: "Review open pull requests labeled angel",
  issue_review: "Review open issues labeled angel",
};

export interface ParsedArguments {
  readonly command: Command;
  readonly dryRun: boolean;
}

export type ParseResult =
  | { readonly kind: "run"; readonly arguments: ParsedArguments }
  | { readonly kind: "help"; readonly text: string };

function isCommand(value: string): value is Command {
  return (COMMANDS as readonly string[]).includes(value);
}

function unknownCommand(argv: readonly string[]): ExitError {
  const given = argv.join(" ") || "(none)";
  return new ExitError(
    1,
    `Unknown command: ${given}. Valid commands: ${COMMANDS.join(", ")}`,
  );
}

function buildProgram(
  write: (text: string) => void,
  onCommand: (parsed: ParsedArguments) => void = () => {},
): Program {
  const program = new Program()
    .name("angel")
    .description(PROGRAM_DESCRIPTION)
    .helpOption("-h, --help", HELP_FLAGS_HELP)
    .configureHelp({ styleTitle: (title) => title.toLowerCase() })
    .configureOutput({ writeOut: write, writeErr: write })
    .option("--dry-run", DRY_RUN_HELP)
    .exitOverride();

  for (const name of COMMANDS) {
    const command = program
      .command(name)
      .description(DESCRIPTIONS[name])
      .summary(SUMMARIES[name]);
    if (name !== "chat") {
      command.option("--dry-run", DRY_RUN_HELP);
    }
    command.action((options: { dryRun?: boolean }) => {
      onCommand({
        command: name,
        dryRun: options.dryRun === true || program.opts().dryRun === true,
      });
    });
  }
  return program;
}

export function topLevelHelp(): string {
  return buildProgram(() => {}).helpInformation();
}

export function commandHelp(command: Command): string {
  const found = buildProgram(() => {}).commands.find((each) => each.name() === command);
  if (found === undefined) {
    throw new Error(`no such command: ${command}`);
  }
  return found.helpInformation();
}

function helpCommand(argv: readonly string[], rest: readonly string[]): ParseResult {
  if (rest.length === 0) {
    return { kind: "help", text: topLevelHelp() };
  }
  const [name] = rest;
  if (rest.length !== 1 || name === undefined || !isCommand(name)) {
    throw unknownCommand(argv);
  }
  return { kind: "help", text: commandHelp(name) };
}

export function parseArguments(argv: readonly string[]): ParseResult {
  if (argv.length === 0) {
    return { kind: "help", text: topLevelHelp() };
  }
  if (argv[0] === "help") {
    return helpCommand(argv, argv.slice(1));
  }
  if (argv.find((argument) => !argument.startsWith("-")) === "chat") {
    if (argv.includes("--dry-run")) {
      throw new ExitError(
        1,
        "--dry-run is not valid for chat: chat makes no GitHub writes",
      );
    }
  }

  let text = "";
  let parsed: ParsedArguments | undefined;
  const program = buildProgram(
    (chunk) => {
      text += chunk;
    },
    (result) => {
      parsed = result;
    },
  );

  try {
    program.parse(argv, { from: "user" });
  } catch (error) {
    if (error instanceof CommanderError && error.code.startsWith("commander.help")) {
      return { kind: "help", text };
    }
    throw unknownCommand(argv);
  }

  if (parsed === undefined) {
    throw unknownCommand(argv);
  }
  return { kind: "run", arguments: parsed };
}

function writeLine(stream: OutputStream, text = ""): void {
  stream.write(`${text}\n`);
}

function count(value: number): string {
  return value.toLocaleString("en-US").padStart(9);
}

export interface Ui {
  readonly run: (command: Command, dryRun: boolean, logPath: string) => void;
  readonly reviews: (
    reviews: readonly Review[],
    dryRun: boolean,
    nothingMessage: string,
  ) => void;
  readonly usage: (totals: UsageTotals) => void;
  readonly failures: (failures: readonly ItemFailure[]) => void;
}

export function terminalUi(stdout: OutputStream, stderr: OutputStream): Ui {
  return {
    run(command, dryRun, logPath) {
      section("Run", stdout);
      writeLine(stdout);
      writeLine(stdout, `  ${"command".padEnd(7)}   ${command}`);
      writeLine(stdout, `  ${"dry run".padEnd(7)}   ${dryRun ? "yes" : "no"}`);
      writeLine(stdout, `  ${"log".padEnd(7)}   ${logPath}`);
    },

    reviews(reviews, dryRun, nothingMessage) {
      section("Reviews", stdout);
      writeLine(stdout);
      if (reviews.length === 0) {
        writeLine(stdout, style(nothingMessage, [DIM], stdout));
        return;
      }
      for (const review of reviews) {
        const label = `${review.target.repository}#${review.target.number}`;
        if (dryRun) {
          writeLine(stdout, style(label, [BOLD], stdout));
          writeLine(stdout, review.body);
          writeLine(stdout);
        } else {
          writeLine(stdout, style(`  Commented on ${label}`, [GREEN], stdout));
        }
      }
    },

    usage(totals) {
      section("Usage", stdout);
      writeLine(stdout);
      writeLine(stdout, `  ${"calls".padEnd(13)}${count(totals.calls)}`);
      writeLine(stdout, `  ${"input_tokens".padEnd(13)}${count(totals.inputTokens)}`);
      writeLine(stdout, `  ${"output_tokens".padEnd(13)}${count(totals.outputTokens)}`);
      writeLine(stdout, `  ${"total_tokens".padEnd(13)}${count(totals.totalTokens)}`);
      writeLine(
        stdout,
        `  ${"duration_ms".padEnd(13)}${totals.durationMs.toFixed(1).padStart(9)}`,
      );
    },

    failures(failures) {
      if (failures.length === 0) {
        return;
      }
      section("Failures", stderr);
      writeLine(stderr);
      for (const failure of failures) {
        const target =
          failure.number === 0
            ? failure.repository
            : `${failure.repository}#${failure.number}`;
        writeLine(
          stderr,
          style(
            `Failed ${failure.stage} for ${target}: ${failure.errorType}: ${failure.error}`,
            [RED],
            stderr,
          ),
        );
      }
    },
  };
}
