import type { OutputStream } from "../../src/console.js";

/** An in-memory {@link OutputStream} that records everything written to it. */
export class MemoryStream implements OutputStream {
  readonly isTTY: boolean;
  private chunks: string[] = [];

  constructor(isTty = false) {
    this.isTTY = isTty;
  }

  write(chunk: string): void {
    this.chunks.push(chunk);
  }

  get text(): string {
    return this.chunks.join("");
  }

  get lines(): string[] {
    return this.text.split("\n");
  }
}
