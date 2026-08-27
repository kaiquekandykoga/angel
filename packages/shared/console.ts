import { loadEnvVar } from "./env.js";

export interface OutputStream {
  write(chunk: string): void;
  readonly isTTY?: boolean | undefined;
}

export const RESET = "0";
export const BOLD = "1";
export const DIM = "2";
export const RED = "31";
export const GREEN = "32";
export const YELLOW = "33";
export const BLUE = "34";
export const MAGENTA = "35";
export const CYAN = "36";

const SECTION_WIDTH = 72;

export function colorEnabled(stream: OutputStream): boolean {
  if (loadEnvVar("NO_COLOR")) {
    return false;
  }
  switch ((loadEnvVar("ANGEL_COLOR") ?? "").trim().toLowerCase()) {
    case "never":
      return false;
    case "always":
      return true;
    default:
      return stream.isTTY === true;
  }
}

export function style(
  text: string,
  codes: readonly string[],
  stream: OutputStream,
): string {
  if (codes.length === 0 || !colorEnabled(stream)) {
    return text;
  }
  return `\x1b[${codes.join(";")}m${text}\x1b[${RESET}m`;
}

export function section(title: string, stream: OutputStream): void {
  const heading =
    title.length >= SECTION_WIDTH
      ? `${title} `
      : `${title} ${"─".repeat(SECTION_WIDTH - title.length - 1)}`;
  stream.write("\n");
  stream.write(`${style(heading, [BOLD, CYAN], stream)}\n`);
}
