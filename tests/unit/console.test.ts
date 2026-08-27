import { beforeEach, describe, expect, it } from "vitest";
import { BOLD, CYAN, colorEnabled, RESET, section, style } from "../../src/console.js";
import { resetEnvCache } from "../../src/env.js";
import { MemoryStream } from "../helpers/stream.js";

const tty = () => new MemoryStream(true);
const plain = () => new MemoryStream(false);

describe("colorEnabled", () => {
  beforeEach(() => {
    resetEnvCache();
    delete process.env.NO_COLOR;
    delete process.env.ANGEL_COLOR;
  });

  it("is false for a non-tty stream", () => {
    expect(colorEnabled(plain())).toBe(false);
  });

  it("is true for a tty stream", () => {
    expect(colorEnabled(tty())).toBe(true);
  });

  it("is false for a tty stream when NO_COLOR is set", () => {
    process.env.NO_COLOR = "1";
    expect(colorEnabled(tty())).toBe(false);
  });

  it("is false when NO_COLOR is set even if ANGEL_COLOR asks for always", () => {
    process.env.NO_COLOR = "1";
    process.env.ANGEL_COLOR = "always";
    expect(colorEnabled(tty())).toBe(false);
  });

  it("ignores an empty NO_COLOR", () => {
    process.env.NO_COLOR = "";
    expect(colorEnabled(tty())).toBe(true);
  });

  it("is true for a non-tty stream when ANGEL_COLOR is always", () => {
    process.env.ANGEL_COLOR = "ALWAYS ";
    expect(colorEnabled(plain())).toBe(true);
  });

  it("is false for a tty stream when ANGEL_COLOR is never", () => {
    process.env.ANGEL_COLOR = "never";
    expect(colorEnabled(tty())).toBe(false);
  });

  it("defers to the stream when ANGEL_COLOR is auto", () => {
    process.env.ANGEL_COLOR = "auto";
    expect(colorEnabled(tty())).toBe(true);
    expect(colorEnabled(plain())).toBe(false);
  });

  it("defers to the stream when ANGEL_COLOR is unrecognised", () => {
    process.env.ANGEL_COLOR = "bogus";
    expect(colorEnabled(tty())).toBe(true);
    expect(colorEnabled(plain())).toBe(false);
  });

  it("is false for a stream that declares no tty flag", () => {
    expect(colorEnabled({ write: () => {} })).toBe(false);
  });
});

describe("style", () => {
  beforeEach(() => {
    resetEnvCache();
    delete process.env.NO_COLOR;
    delete process.env.ANGEL_COLOR;
  });

  it("returns the text unchanged when color is disabled", () => {
    expect(style("hello", [BOLD], plain())).toBe("hello");
  });

  it("returns the text unchanged when no codes are given", () => {
    expect(style("hello", [], tty())).toBe("hello");
  });

  it("wraps the text in the joined codes when color is enabled", () => {
    expect(style("hello", [BOLD, CYAN], tty())).toBe("\x1b[1;36mhello\x1b[0m");
  });
});

describe("section", () => {
  beforeEach(() => {
    resetEnvCache();
    delete process.env.NO_COLOR;
    delete process.env.ANGEL_COLOR;
  });

  it("writes a heading padded with a rule", () => {
    const stream = plain();
    section("Reviews", stream);
    expect(stream.text).toContain("Reviews ─────");
    expect(stream.text).not.toContain("\x1b");
  });

  it("writes a blank line before the heading", () => {
    const stream = plain();
    section("Reviews", stream);
    expect(stream.text.startsWith("\n")).toBe(true);
  });

  it("does not pad a title as wide as the rule", () => {
    const stream = plain();
    section("x".repeat(80), stream);
    expect(stream.text).not.toContain("─");
  });

  it("styles the heading when color is enabled", () => {
    const stream = tty();
    section("Reviews", stream);
    expect(stream.text).toContain(`\x1b[${BOLD};${CYAN}m`);
    expect(stream.text.trimEnd().endsWith(`\x1b[${RESET}m`)).toBe(true);
  });
});
