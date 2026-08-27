import type { OutputStream } from "../../packages/shared/console.js";

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
