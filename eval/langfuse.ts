import { LangfuseClient } from "@langfuse/client";
import { LangfuseSpanProcessor } from "@langfuse/otel";
import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import { loadEnvVar } from "../packages/shared/env.js";

export const LANGFUSE_BASE_URL_DEFAULT = "https://cloud.langfuse.com";

export class MissingLangfuseCredentialsError extends Error {
  override readonly name = "MissingLangfuseCredentialsError";
}

export interface Tracing {
  readonly client: LangfuseClient;
  shutdown(): Promise<void>;
}

export function startTracing(): Tracing {
  const publicKey = loadEnvVar("LANGFUSE_PUBLIC_KEY");
  const secretKey = loadEnvVar("LANGFUSE_SECRET_KEY");
  const baseUrl = loadEnvVar("LANGFUSE_BASE_URL") || LANGFUSE_BASE_URL_DEFAULT;
  if (!publicKey || !secretKey) {
    throw new MissingLangfuseCredentialsError(
      "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY environment variables are not set.",
    );
  }

  const provider = new NodeTracerProvider({
    spanProcessors: [
      new LangfuseSpanProcessor({
        publicKey,
        secretKey,
        baseUrl,
        exportMode: "immediate",
      }),
    ],
  });
  provider.register();

  const client = new LangfuseClient({ publicKey, secretKey, baseUrl });
  return {
    client,
    async shutdown(): Promise<void> {
      await client.shutdown();
      await provider.shutdown();
    },
  };
}
