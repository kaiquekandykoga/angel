import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { loadEnvVar, resetEnvCache } from "../../src/env.js";
import { useTemporaryDirectory } from "../helpers/tmp.js";

describe("loadEnvVar", () => {
  const temporary = useTemporaryDirectory();

  beforeEach(() => {
    resetEnvCache();
  });

  it("returns undefined when the variable is not set anywhere", () => {
    expect(loadEnvVar("ANGEL_TEST_ABSENT")).toBeUndefined();
  });

  it("returns the value already present in the environment", () => {
    process.env.ANGEL_TEST_PRESENT = "from-environment";
    expect(loadEnvVar("ANGEL_TEST_PRESENT")).toBe("from-environment");
    delete process.env.ANGEL_TEST_PRESENT;
  });

  it("reads a variable from a .env file in the current directory", () => {
    writeFileSync(join(temporary.path, ".env"), "ANGEL_TEST_DOTENV=from-file\n");
    expect(loadEnvVar("ANGEL_TEST_DOTENV")).toBe("from-file");
    delete process.env.ANGEL_TEST_DOTENV;
  });

  it("searches parent directories for the .env file", () => {
    writeFileSync(join(temporary.path, ".env"), "ANGEL_TEST_PARENT=from-parent\n");
    const nested = join(temporary.path, "a", "b");
    mkdirSync(nested, { recursive: true });
    process.chdir(nested);

    expect(loadEnvVar("ANGEL_TEST_PARENT")).toBe("from-parent");
    delete process.env.ANGEL_TEST_PARENT;
  });

  it("lets an exported variable win over the .env file", () => {
    writeFileSync(join(temporary.path, ".env"), "ANGEL_TEST_WINS=from-file\n");
    process.env.ANGEL_TEST_WINS = "from-environment";

    expect(loadEnvVar("ANGEL_TEST_WINS")).toBe("from-environment");
    delete process.env.ANGEL_TEST_WINS;
  });
});
