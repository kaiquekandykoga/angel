import { z } from "zod";

const commentSchema = z.strictObject({
  author: z.string(),
  body: z.string(),
  createdAt: z.string(),
});

export const prReviewInputSchema = z.strictObject({
  repository: z.string(),
  number: z.number().int(),
  title: z.string(),
  body: z.string(),
  headSha: z.string(),
  diff: z.string(),
  comments: z.array(commentSchema),
});

export type PrReviewInput = z.infer<typeof prReviewInputSchema>;

export const issueReviewInputSchema = z.strictObject({
  repository: z.string(),
  number: z.number().int(),
  title: z.string(),
  body: z.string(),
  updatedAt: z.string(),
  comments: z.array(commentSchema),
});

export type IssueReviewInput = z.infer<typeof issueReviewInputSchema>;

/**
 * What a good review is expected to reach. `files` are diff paths a finding should
 * cite; `keywords` are lowercase substrings the rendered review should contain, so
 * stems ("reproduc") match every inflection.
 */
export const expectedReviewSchema = z.strictObject({
  files: z.array(z.string()),
  keywords: z.array(z.string()),
});

export type ExpectedReview = z.infer<typeof expectedReviewSchema>;

export interface EvalItem<Input> {
  readonly input: Input;
  readonly expectedOutput: ExpectedReview;
  readonly metadata: { readonly case: string };
}

const SQL_INJECTION_DIFF = `diff --git a/src/users.ts b/src/users.ts
--- a/src/users.ts
+++ b/src/users.ts
@@ -12,6 +12,11 @@ export class UserRepository {
     return this.db.query("SELECT * FROM users WHERE id = $1", [id]);
   }
 
+  async searchByName(name: string): Promise<User[]> {
+    const sql = "SELECT * FROM users WHERE name LIKE '%" + name + "%'";
+    return this.db.query(sql);
+  }
+
   async delete(id: string): Promise<void> {
     return this.db.query("DELETE FROM users WHERE id = $1", [id]);
   }
`;

const DROPPED_AWAIT_DIFF = `diff --git a/src/queue.ts b/src/queue.ts
--- a/src/queue.ts
+++ b/src/queue.ts
@@ -20,5 +20,6 @@ export class JobQueue {
   async enqueue(job: Job): Promise<void> {
-    await this.store.save(job);
+    this.store.save(job);
+    this.metrics.increment("jobs.enqueued");
     this.logger.info("queued", { id: job.id });
   }
 }
`;

const SEQUENTIAL_FETCH_DIFF = `diff --git a/src/report.ts b/src/report.ts
--- a/src/report.ts
+++ b/src/report.ts
@@ -8,3 +8,6 @@ export async function buildReport(ids: string[]) {
-  const users = await client.fetchUsers(ids);
+  const users: User[] = [];
+  for (const id of ids) {
+    users.push(await client.fetchUser(id));
+  }
   return users.map(toRow);
 }
`;

export const PR_REVIEW_ITEMS: readonly EvalItem<PrReviewInput>[] = [
  {
    metadata: { case: "sql-injection" },
    input: {
      repository: "angel-eval/shop",
      number: 101,
      title: "Add user search",
      body: "Lets support looking users up by name.",
      headSha: "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678",
      diff: SQL_INJECTION_DIFF,
      comments: [],
    },
    expectedOutput: {
      files: ["src/users.ts"],
      keywords: ["injection", "parameter"],
    },
  },
  {
    metadata: { case: "dropped-await" },
    input: {
      repository: "angel-eval/shop",
      number: 102,
      title: "Count enqueued jobs",
      body: "Adds a metric for every enqueued job.",
      headSha: "b2c3d4e5f60718293a4b5c6d7e8f901234567890",
      diff: DROPPED_AWAIT_DIFF,
      comments: [
        {
          author: "maintainer",
          body: "Metric name looks right to me.",
          createdAt: "2026-08-01T10:00:00Z",
        },
      ],
    },
    expectedOutput: {
      files: ["src/queue.ts"],
      keywords: ["await", "promise"],
    },
  },
  {
    metadata: { case: "sequential-fetch" },
    input: {
      repository: "angel-eval/shop",
      number: 103,
      title: "Build the report row by row",
      body: "The batch endpoint was flaky, so fetch each user instead.",
      headSha: "c3d4e5f60718293a4b5c6d7e8f90123456789012",
      diff: SEQUENTIAL_FETCH_DIFF,
      comments: [],
    },
    expectedOutput: {
      files: ["src/report.ts"],
      keywords: ["loop", "sequential"],
    },
  },
];

export const ISSUE_REVIEW_ITEMS: readonly EvalItem<IssueReviewInput>[] = [
  {
    metadata: { case: "unmeasurable-goal" },
    input: {
      repository: "angel-eval/shop",
      number: 201,
      title: "Make login faster",
      body: "Login feels slow. Please speed it up.",
      updatedAt: "2026-08-02T09:00:00Z",
      comments: [],
    },
    expectedOutput: {
      files: [],
      keywords: ["measur", "latency"],
    },
  },
  {
    metadata: { case: "missing-repro" },
    input: {
      repository: "angel-eval/shop",
      number: 202,
      title: "App crashes sometimes",
      body: "It crashed again today. Same as before.",
      updatedAt: "2026-08-03T09:00:00Z",
      comments: [
        {
          author: "reporter",
          body: "Happened twice this week.",
          createdAt: "2026-08-03T08:00:00Z",
        },
      ],
    },
    expectedOutput: {
      files: [],
      keywords: ["reproduc", "version"],
    },
  },
];
