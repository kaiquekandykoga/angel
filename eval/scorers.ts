import type { Finding, IssueReviewOutput } from "../apps/server/index.js";

export interface Score {
  readonly name: string;
  readonly value: number;
  readonly comment: string;
}

export interface Hunk {
  readonly start: number;
  readonly end: number;
}

const NEW_FILE_HEADER = /^\+\+\+ (?:b\/)?(.+)$/;
const HUNK_HEADER = /^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@/;

export function parseDiff(diff: string): Map<string, Hunk[]> {
  const files = new Map<string, Hunk[]>();
  let current: Hunk[] | undefined;
  for (const line of diff.split("\n")) {
    if (line.startsWith("+++ ")) {
      const path = NEW_FILE_HEADER.exec(line)?.[1];
      if (path === undefined || path === "/dev/null") {
        current = undefined;
        continue;
      }
      current = files.get(path) ?? [];
      files.set(path, current);
      continue;
    }
    const hunk = HUNK_HEADER.exec(line);
    if (hunk?.[1] === undefined || current === undefined) {
      continue;
    }
    const start = Number(hunk[1]);
    const count = hunk[2] === undefined ? 1 : Number(hunk[2]);
    current.push({ start, end: start + Math.max(count, 1) - 1 });
  }
  return files;
}

function ratio(name: string, hits: number, total: number, unit: string): Score[] {
  if (total === 0) {
    return [];
  }
  return [{ name, value: hits / total, comment: `${hits} of ${total} ${unit}` }];
}

interface Citation {
  readonly file: string;
  readonly line: number | null;
}

function citations(findings: readonly Finding[]): Citation[] {
  return findings.flatMap((finding) =>
    finding.file === null ? [] : [{ file: finding.file, line: finding.line }],
  );
}

export function citedFilesInDiff(findings: readonly Finding[], diff: string): Score[] {
  const files = parseDiff(diff);
  const cited = citations(findings);
  const grounded = cited.filter((citation) => files.has(citation.file));
  return ratio(
    "cited_files_in_diff",
    grounded.length,
    cited.length,
    "cited files are touched by the diff",
  );
}

export function citedLinesInHunks(findings: readonly Finding[], diff: string): Score[] {
  const files = parseDiff(diff);
  const located = citations(findings).flatMap((citation) =>
    citation.line === null ? [] : [{ file: citation.file, line: citation.line }],
  );
  const inside = located.filter((citation) =>
    (files.get(citation.file) ?? []).some(
      (hunk) => citation.line >= hunk.start && citation.line <= hunk.end,
    ),
  );
  return ratio(
    "cited_lines_in_hunks",
    inside.length,
    located.length,
    "cited lines fall inside a changed hunk",
  );
}

export function expectedFilesFlagged(
  findings: readonly Finding[],
  expected: readonly string[],
): Score[] {
  const cited = new Set(citations(findings).map((citation) => citation.file));
  const flagged = expected.filter((file) => cited.has(file));
  return ratio(
    "expected_files_flagged",
    flagged.length,
    expected.length,
    "expected files are cited by a finding",
  );
}

export function expectedKeywordsMentioned(
  body: string,
  expected: readonly string[],
): Score[] {
  const haystack = body.toLowerCase();
  const mentioned = expected.filter((keyword) =>
    haystack.includes(keyword.toLowerCase()),
  );
  return ratio(
    "expected_keywords_mentioned",
    mentioned.length,
    expected.length,
    `expected keywords appear in the review (missing: ${
      expected.filter((keyword) => !mentioned.includes(keyword)).join(", ") || "none"
    })`,
  );
}

export function lensesCovered(body: string, lenses: readonly string[]): Score[] {
  const haystack = body.toLowerCase();
  const covered = lenses.filter((lens) =>
    haystack.includes(`### ${lens.toLowerCase()}`),
  );
  return ratio(
    "lenses_covered",
    covered.length,
    lenses.length,
    "lenses have a section in the posted body",
  );
}

export function findingCount(findings: readonly Finding[]): Score {
  return {
    name: "finding_count",
    value: findings.length,
    comment: `${findings.length} findings across the review`,
  };
}

export function acceptanceCriteriaCount(output: IssueReviewOutput): Score {
  const count = output.acceptanceCriteria.length;
  return {
    name: "acceptance_criteria_count",
    value: count,
    comment: `${count} acceptance criteria proposed`,
  };
}

export function suggestedApproachPresent(output: IssueReviewOutput): Score {
  const present = output.suggestedApproach.trim() !== "";
  return {
    name: "suggested_approach_present",
    value: present ? 1 : 0,
    comment: present ? "an approach was suggested" : "no approach was suggested",
  };
}
