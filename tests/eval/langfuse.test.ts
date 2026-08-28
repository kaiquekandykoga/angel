import { describe, expect, it, vi } from "vitest";
import { startTracing } from "../../eval/langfuse.js";

function stubKeys(publicKey: string, secretKey: string): void {
  vi.stubEnv("LANGFUSE_PUBLIC_KEY", publicKey);
  vi.stubEnv("LANGFUSE_SECRET_KEY", secretKey);
  vi.stubEnv("LANGFUSE_BASE_URL", "http://langfuse.invalid");
}

describe("startTracing", () => {
  it("refuses to start without both keys", () => {
    stubKeys("pk-lf-test", "");

    expect(() => startTracing()).toThrow(/LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY/);
  });

  it("hands back a client that shuts down cleanly", async () => {
    stubKeys("pk-lf-test", "sk-lf-test");

    const tracing = startTracing();

    await expect(tracing.shutdown()).resolves.toBeUndefined();
  });
});
