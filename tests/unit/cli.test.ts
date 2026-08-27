import { describe, expect, it } from "vitest";
import { commandHelp, ExitError, parseArguments, topLevelHelp } from "../../src/cli.js";

function parse(...argv: string[]) {
  return parseArguments(argv);
}

describe("parseArguments", () => {
  it.each(["chat", "pr_review", "issue_review"] as const)(
    "accepts the %s command",
    (command) => {
      expect(parse(command)).toEqual({
        kind: "run",
        arguments: { command, dryRun: false },
      });
    },
  );

  it("accepts --dry-run after the command", () => {
    expect(parse("pr_review", "--dry-run")).toMatchObject({
      arguments: { command: "pr_review", dryRun: true },
    });
  });

  it("accepts --dry-run before the command", () => {
    expect(parse("--dry-run", "issue_review")).toMatchObject({
      arguments: { command: "issue_review", dryRun: true },
    });
  });

  it("rejects --dry-run for chat", () => {
    expect(() => parse("chat", "--dry-run")).toThrow(
      "--dry-run is not valid for chat: chat makes no GitHub writes",
    );
  });

  it("prints the top-level help when given nothing", () => {
    expect(parse()).toEqual({ kind: "help", text: topLevelHelp() });
  });

  it.each(["-h", "--help"])("prints the top-level help for %s", (flag) => {
    expect(parse(flag)).toEqual({ kind: "help", text: topLevelHelp() });
  });

  it("prints the top-level help for a bare help", () => {
    expect(parse("help")).toEqual({ kind: "help", text: topLevelHelp() });
  });

  it("prints a command's help for help <command>", () => {
    expect(parse("help", "pr_review")).toEqual({
      kind: "help",
      text: commandHelp("pr_review"),
    });
  });

  it("prints a command's help for <command> --help", () => {
    expect(parse("issue_review", "--help")).toEqual({
      kind: "help",
      text: commandHelp("issue_review"),
    });
  });

  it.each([["bogus"], ["help", "bogus"], ["help", "chat", "extra"], ["--bogus"]])(
    "exits 1 for %s",
    (...argv: string[]) => {
      const error = (() => {
        try {
          parseArguments(argv);
        } catch (thrown) {
          return thrown;
        }
        return undefined;
      })();

      expect(error).toBeInstanceOf(ExitError);
      expect(error).toMatchObject({ code: 1 });
      expect((error as ExitError).message).toContain("Unknown command");
      expect((error as ExitError).message).toContain(
        "Valid commands: chat, pr_review, issue_review",
      );
    },
  );

  it("names what was given in the unknown-command message", () => {
    expect(() => parse("bogus", "args")).toThrow("Unknown command: bogus args.");
  });

  it("rejects a second command", () => {
    expect(() => parse("chat", "pr_review")).toThrow("Unknown command");
  });
});

describe("the help screens", () => {
  it("list every command at the top level", () => {
    const text = topLevelHelp();

    expect(text).toContain("chat");
    expect(text).toContain("pr_review");
    expect(text).toContain("issue_review");
    expect(text).toContain("--dry-run");
  });

  it("offer --dry-run on the review commands", () => {
    expect(commandHelp("pr_review")).toContain("--dry-run");
    expect(commandHelp("issue_review")).toContain("--dry-run");
  });

  it("do not offer --dry-run on chat", () => {
    expect(commandHelp("chat")).not.toContain("--dry-run");
  });

  it("name the command in its own usage line", () => {
    expect(commandHelp("pr_review").startsWith("usage: angel pr_review")).toBe(true);
  });
});
