import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/**/*.test.ts"],
    environment: "node",
    restoreMocks: true,
    unstubEnvs: true,
    coverage: {
      provider: "v8",
      include: ["apps/**/*.ts", "packages/**/*.ts", "eval/**/*.ts"],
      reporter: ["text", "lcov"],
    },
  },
});
