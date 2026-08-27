import { z } from "zod";
import { type ContextLogger, getLogger } from "../../../packages/shared/logs.js";
import { namedSchema } from "../clients/llm.js";
import type { Comment, GitHubClient, ReviewTarget } from "../external/github/client.js";

const logger = getLogger("angel.agents.shared");

export const SEVERITIES = ["blocker", "major", "minor", "nit"] as const;

export type Severity = (typeof SEVERITIES)[number];

export const findingSchema = z.strictObject({
  severity: z.enum(SEVERITIES).describe("How serious this finding is."),
  title: z.string().describe("A short one-line summary of the finding."),
  detail: z.string().describe("A detailed explanation of the finding."),
  file: z
    .string()
    .nullable()
    .default(null)
    .describe("The path of the file this finding refers to, if any."),
  line: z
    .number()
    .int()
    .nullable()
    .default(null)
    .describe("The line number this finding refers to, if any."),
});

export type Finding = z.infer<typeof findingSchema>;

export const pullRequestReviewOutputSchema = z.strictObject({
  summary: z.string().describe("A short overall summary of the pull request review."),
  findings: z
    .array(findingSchema)
    .default([])
    .describe("Specific findings from the review."),
});

export type PullRequestReviewOutput = z.infer<typeof pullRequestReviewOutputSchema>;

export const PULL_REQUEST_REVIEW_OUTPUT = namedSchema(
  "PullRequestReviewOutput",
  pullRequestReviewOutputSchema,
);

export const issueReviewOutputSchema = z.strictObject({
  summary: z.string().describe("A short overall summary of the issue review."),
  findings: z
    .array(findingSchema)
    .default([])
    .describe("Specific findings from the review."),
  acceptanceCriteria: z
    .array(z.string())
    .default([])
    .describe("Acceptance criteria the issue should satisfy."),
  suggestedApproach: z
    .string()
    .default("")
    .describe("A suggested approach for resolving the issue."),
});

export type IssueReviewOutput = z.infer<typeof issueReviewOutputSchema>;

export const ISSUE_REVIEW_OUTPUT = namedSchema(
  "IssueReviewOutput",
  issueReviewOutputSchema,
);

export function renderFinding(finding: Finding): string {
  let location = "";
  if (finding.file !== null) {
    location = ` — \`${finding.file}`;
    if (finding.line !== null) {
      location += `:${finding.line}`;
    }
    location += "`";
  }
  return `**[${finding.severity}] ${finding.title}**${location}\n${finding.detail}`;
}

function renderFindingsSection(findings: readonly Finding[]): string {
  if (findings.length === 0) {
    return "No findings.";
  }
  return `### Findings\n\n${findings.map(renderFinding).join("\n\n")}`;
}

export function renderIssueReview(output: IssueReviewOutput): string {
  const sections = [output.summary, renderFindingsSection(output.findings)];
  if (output.acceptanceCriteria.length > 0) {
    const criteria = output.acceptanceCriteria.map((item) => `- ${item}`).join("\n");
    sections.push(`### Acceptance criteria\n\n${criteria}`);
  }
  if (output.suggestedApproach !== "") {
    sections.push(`### Suggested approach\n\n${output.suggestedApproach}`);
  }
  return sections.join("\n\n");
}

export interface Review {
  readonly target: ReviewTarget;
  readonly body: string;
}

export interface ItemFailure {
  readonly repository: string;
  readonly number: number;
  readonly stage: string;
  readonly errorType: string;
  readonly error: string;
}

export interface FailureDetails {
  readonly stage: string;
  readonly repository: string;
  readonly number: number;
}

function describe(error: unknown): { errorType: string; error: string } {
  if (error instanceof Error) {
    return { errorType: error.name, error: error.message };
  }
  return { errorType: typeof error, error: String(error) };
}

export async function collectFailures(
  failures: ItemFailure[],
  message: string,
  details: FailureDetails,
  work: () => Promise<void>,
): Promise<boolean> {
  try {
    await work();
    return true;
  } catch (error) {
    const described = describe(error);
    logger.warning(message, {
      repository: details.repository,
      number: details.number,
      stage: details.stage,
      error_type: described.errorType,
      error: described.error,
    });
    failures.push({ ...details, ...described });
    return false;
  }
}

export interface ReviewProduced {
  readonly repository: string;
  readonly number: number;
  readonly review: string;
  readonly findings: readonly Finding[];
  readonly lens?: string;
}

export function logReviewProduced(log: ContextLogger, produced: ReviewProduced): void {
  const severityCounts: Record<string, number> = {};
  for (const finding of produced.findings) {
    severityCounts[finding.severity] = (severityCounts[finding.severity] ?? 0) + 1;
  }
  const context: Record<string, unknown> = {
    repository: produced.repository,
    number: produced.number,
    review: produced.review,
    finding_count: produced.findings.length,
    severity_counts: severityCounts,
  };
  if (produced.lens) {
    context.lens = produced.lens;
  }
  log.debug("review produced", context);
}

export function lastReviewAt(
  comments: readonly Comment[],
  reviewerLogin: string,
): string | undefined {
  const timestamps = comments
    .filter((comment) => comment.author === reviewerLogin)
    .map((comment) => comment.createdAt);
  return timestamps.length === 0 ? undefined : timestamps.reduce(max);
}

function max(a: string, b: string): string {
  return b > a ? b : a;
}

const MARKER_PATTERN = /<!-- angel: sha=(\S+) -->/g;

export function reviewMarker(sha: string): string {
  return `<!-- angel: sha=${sha} -->`;
}

export function reviewedSha(
  comments: readonly Comment[],
  reviewerLogin: string,
): string | undefined {
  let latest: { createdAt: string; sha: string } | undefined;
  for (const comment of comments) {
    if (comment.author !== reviewerLogin) {
      continue;
    }
    const matches = [...comment.body.matchAll(MARKER_PATTERN)];
    const last = matches.at(-1);
    if (last?.[1] === undefined) {
      continue;
    }
    if (latest === undefined || comment.createdAt > latest.createdAt) {
      latest = { createdAt: comment.createdAt, sha: last[1] };
    }
  }
  return latest?.sha;
}

export function renderComments(comments: readonly Comment[]): string {
  if (comments.length === 0) {
    return "(none)";
  }
  return comments.map((comment) => `@${comment.author}: ${comment.body}`).join("\n\n");
}

export interface ReviewState {
  readonly reviews: Review[];
}

export function postReviewComments(github: GitHubClient) {
  return async (state: ReviewState): Promise<{ failures: ItemFailure[] }> => {
    const { reviews } = state;
    logger.info(`posting ${reviews.length} review comments`);
    const failures: ItemFailure[] = [];
    for (const review of reviews) {
      const target = review.target;
      logger.debug("posting comment", {
        repository: target.repository,
        number: target.number,
        body_length: review.body.length,
      });
      await collectFailures(
        failures,
        "failed to post comment",
        {
          stage: "post_review_comments",
          repository: target.repository,
          number: target.number,
        },
        async () => {
          await github.postComment(target, review.body);
          logger.info(`posted ${target.repository}#${target.number}`);
        },
      );
    }
    return { failures };
  };
}
