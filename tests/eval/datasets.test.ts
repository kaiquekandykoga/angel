import { describe, expect, it } from "vitest";
import {
  ISSUE_REVIEW_ITEMS,
  issueReviewInputSchema,
  PR_REVIEW_ITEMS,
  prReviewInputSchema,
} from "../../eval/datasets.js";
import { parseDiff } from "../../eval/scorers.js";

describe("the pull request dataset", () => {
  it.each(PR_REVIEW_ITEMS)("$metadata.case parses", (item) => {
    expect(() => prReviewInputSchema.parse(item.input)).not.toThrow();
  });

  it.each(PR_REVIEW_ITEMS)("$metadata.case expects files its diff touches", (item) => {
    const touched = [...parseDiff(item.input.diff).keys()];

    expect(item.expectedOutput.files).not.toEqual([]);
    for (const file of item.expectedOutput.files) {
      expect(touched).toContain(file);
    }
  });

  it.each(PR_REVIEW_ITEMS)("$metadata.case expects lowercase keywords", (item) => {
    for (const keyword of item.expectedOutput.keywords) {
      expect(keyword).toBe(keyword.toLowerCase());
    }
  });
});

describe("the issue dataset", () => {
  it.each(ISSUE_REVIEW_ITEMS)("$metadata.case parses", (item) => {
    expect(() => issueReviewInputSchema.parse(item.input)).not.toThrow();
  });

  it.each(ISSUE_REVIEW_ITEMS)("$metadata.case expects lowercase keywords", (item) => {
    expect(item.expectedOutput.keywords).not.toEqual([]);
    for (const keyword of item.expectedOutput.keywords) {
      expect(keyword).toBe(keyword.toLowerCase());
    }
  });
});

describe("both datasets", () => {
  it("names every case once", () => {
    const names = [...PR_REVIEW_ITEMS, ...ISSUE_REVIEW_ITEMS].map(
      (item) => item.metadata.case,
    );

    expect(new Set(names).size).toBe(names.length);
  });
});
