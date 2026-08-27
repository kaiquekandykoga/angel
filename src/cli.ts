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

function isCommand(value: string): value is Command {
  return (COMMANDS as readonly string[]).includes(value);
}

export function topLevelHelp(): string {
  const commands = COMMANDS.map(
    (command) => `    ${command.padEnd(13)} ${SUMMARIES[command]}`,
  ).join("\n");
  return [
    "usage: angel [-h] [--dry-run] <command> ...",
    "",
    "Chat with the model, or review labeled pull requests and issues.",
    "",
    "positional arguments:",
    "  <command>",
    commands,
    "",
    "options:",
    "  -h, --help  show this help message and exit",
    `  --dry-run   ${DRY_RUN_HELP}`,
    "",
    "Run 'angel help <command>' or 'angel <command> --help' for the options of",
    "one command.",
    "",
  ].join("\n");
}

export function commandHelp(command: Command): string {
  const usage =
    command === "chat"
      ? "usage: angel chat [-h]"
      : `usage: angel ${command} [-h] [--dry-run]`;
  const lines = [
    usage,
    "",
    DESCRIPTIONS[command],
    "",
    "options:",
    "  -h, --help  show this help message and exit",
  ];
  if (command !== "chat") {
    lines.push(`  --dry-run   ${DRY_RUN_HELP}`);
  }
  lines.push("");
  return lines.join("\n");
}

export interface ParsedArguments {
  readonly command: Command;
  readonly dryRun: boolean;
}

export type ParseResult =
  | { readonly kind: "run"; readonly arguments: ParsedArguments }
  | { readonly kind: "help"; readonly text: string };

function unknownCommand(argv: readonly string[]): ExitError {
  const given = argv.join(" ") || "(none)";
  return new ExitError(
    1,
    `Unknown command: ${given}. Valid commands: ${COMMANDS.join(", ")}`,
  );
}

export function parseArguments(argv: readonly string[]): ParseResult {
  if (argv.length === 0) {
    return { kind: "help", text: topLevelHelp() };
  }

  if (argv[0] === "help") {
    const rest = argv.slice(1);
    if (rest.length === 0) {
      return { kind: "help", text: topLevelHelp() };
    }
    const [name] = rest;
    if (rest.length !== 1 || name === undefined || !isCommand(name)) {
      throw unknownCommand(argv);
    }
    return { kind: "help", text: commandHelp(name) };
  }

  let command: Command | undefined;
  let dryRun = false;
  for (const argument of argv) {
    if (argument === "-h" || argument === "--help") {
      return {
        kind: "help",
        text: command === undefined ? topLevelHelp() : commandHelp(command),
      };
    }
    if (argument === "--dry-run") {
      dryRun = true;
      continue;
    }
    if (command === undefined && isCommand(argument)) {
      command = argument;
      continue;
    }
    throw unknownCommand(argv);
  }

  if (command === undefined) {
    throw unknownCommand(argv);
  }
  if (dryRun && command === "chat") {
    throw new ExitError(
      1,
      "--dry-run is not valid for chat: chat makes no GitHub writes",
    );
  }
  return { kind: "run", arguments: { command, dryRun } };
}
