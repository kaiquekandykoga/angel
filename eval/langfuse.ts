import { LangfuseClient } from "@langfuse/client";
import { LangfuseSpanProcessor } from "@langfuse/otel";
import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import { loadEnvVar } from "../packages/shared/env.js";

export const LANGFUSE_BASE_URL_DEFAULT = "http://localhost:3000";

export const LANGFUSE_LOCAL_PUBLIC_KEY = "pk-lf-angel-local";
export const LANGFUSE_LOCAL_SECRET_KEY = "sk-lf-angel-local";

export class MissingLangfuseCredentialsError extends Error {
  override readonly name = "MissingLangfuseCredentialsError";
}

export interface LangfuseCredentials {
  readonly publicKey: string;
  readonly secretKey: string;
  readonly baseUrl: string;
}

export interface Tracing {
  readonly client: LangfuseClient;
  readonly baseUrl: string;
  shutdown(): Promise<void>;
}

export function resolveCredentials(): LangfuseCredentials {
  const baseUrl = loadEnvVar("LANGFUSE_BASE_URL") || LANGFUSE_BASE_URL_DEFAULT;
  const publicKey = loadEnvVar("LANGFUSE_PUBLIC_KEY") || "";
  const secretKey = loadEnvVar("LANGFUSE_SECRET_KEY") || "";
  if (!publicKey && !secretKey && baseUrl === LANGFUSE_BASE_URL_DEFAULT) {
    return {
      publicKey: LANGFUSE_LOCAL_PUBLIC_KEY,
      secretKey: LANGFUSE_LOCAL_SECRET_KEY,
      baseUrl,
    };
  }
  if (!publicKey || !secretKey) {
    throw new MissingLangfuseCredentialsError(
      `LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY environment variables are not set. Set both for ${baseUrl}, or unset all three to report to the local Langfuse started by \`npm run eval:up\`.`,
    );
  }
  return { publicKey, secretKey, baseUrl };
}

export function startTracing(): Tracing {
  const { publicKey, secretKey, baseUrl } = resolveCredentials();

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
    baseUrl,
    async shutdown(): Promise<void> {
      await client.shutdown();
      await provider.shutdown();
    },
  };
}
