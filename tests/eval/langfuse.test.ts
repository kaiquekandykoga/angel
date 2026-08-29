import { describe, expect, it, vi } from "vitest";
import {
  LANGFUSE_BASE_URL_DEFAULT,
  resolveCredentials,
  startTracing,
} from "../../eval/langfuse.js";

function stubKeys(
  publicKey: string,
  secretKey: string,
  baseUrl = "http://langfuse.invalid",
): void {
  vi.stubEnv("LANGFUSE_PUBLIC_KEY", publicKey);
  vi.stubEnv("LANGFUSE_SECRET_KEY", secretKey);
  vi.stubEnv("LANGFUSE_BASE_URL", baseUrl);
}

describe("resolveCredentials", () => {
  it("defaults to a Langfuse on localhost when no base URL is set", () => {
    stubKeys("pk-lf-local", "sk-lf-local", "");

    expect(resolveCredentials()).toEqual({
      publicKey: "pk-lf-local",
      secretKey: "sk-lf-local",
      baseUrl: LANGFUSE_BASE_URL_DEFAULT,
    });
  });

  it("reports to the configured instance", () => {
    stubKeys("pk-lf-cloud", "sk-lf-cloud", "https://cloud.langfuse.com");

    expect(resolveCredentials()).toEqual({
      publicKey: "pk-lf-cloud",
      secretKey: "sk-lf-cloud",
      baseUrl: "https://cloud.langfuse.com",
    });
  });

  it("refuses to guess keys, naming the instance it needs them for", () => {
    stubKeys("", "", "https://cloud.langfuse.com");

    expect(() => resolveCredentials()).toThrow(/https:\/\/cloud\.langfuse\.com/);
  });

  it("refuses a half-configured instance", () => {
    stubKeys("pk-lf-test", "", LANGFUSE_BASE_URL_DEFAULT);

    expect(() => resolveCredentials()).toThrow(
      /LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY/,
    );
  });
});

describe("startTracing", () => {
  it("refuses to start without both keys", () => {
    stubKeys("pk-lf-test", "");

    expect(() => startTracing()).toThrow(/LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY/);
  });

  it("hands back a client that shuts down cleanly", async () => {
    stubKeys("pk-lf-test", "sk-lf-test");

    const tracing = startTracing();

    expect(tracing.baseUrl).toBe("http://langfuse.invalid");
    await expect(tracing.shutdown()).resolves.toBeUndefined();
  });
});
