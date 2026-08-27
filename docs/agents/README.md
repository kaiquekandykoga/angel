# Agents

Each command is a [LangGraph](https://langchain-ai.github.io/langgraphjs/) state graph, one
directory under `apps/server/agents/`.

- [`CHAT.md`](CHAT.md) — the interactive REPL, one node, one thread.
- [`PR-REVIEW.md`](PR-REVIEW.md) — open pull requests labeled `angel`, three lenses each.
- [`ISSUE-REVIEW.md`](ISSUE-REVIEW.md) — open issues labeled `angel`, one pass each.

## File conventions

Inside each agent directory, `graph.ts` wires the nodes, `state.ts` declares the state
threaded between them, `prompts.ts` holds the system prompt, and `nodes.ts` holds factories
that take their dependencies (LLM client, GitHub client) and return the node function, so a
graph can be built against fakes in tests. Shared across agents — the `Review` record,
`ItemFailure`, `postReviewComments`, comment helpers, review output schemas and their
markdown renderers — lives in `agents/shared.ts`. Where the clients those factories take sit
is in [`LAYOUT.md`](../LAYOUT.md).

## Structured output

Both review agents ask the model for a schema, not prose: `LlmClient.completeStructured`
binds the OpenAI-style `response_format` json_schema for `PullRequestReviewOutput` /
`IssueReviewOutput` and validates the reply against that [zod](https://zod.dev) schema
itself, rather than through LangChain's `withStructuredOutput` — whose fallback chain
retries a truncated reply with `guided_json`, a format the hosted endpoint rejects, turning
a truncation into a misleading `400 unknown field guided_json`. A completion stopped by the
token ceiling raises `TruncatedCompletionError`; a reply that doesn't fit the schema raises
a zod validation error — either way the item is recorded as a failure instead of posted. The
comment body is rendered from the validated object — `pr_review` merges its three lens
objects into one body in `agents/pr-review/nodes.ts`, `issue_review` renders its single
object with `renderIssueReview`.

The endpoint is OpenAI-compatible, so the model is a `ChatOpenAI` from `@langchain/openai`
pointed at `https://integrate.api.nvidia.com/v1`; the client seam in
`external/nvidia/client.ts` is one `invoke(messages, options)` method, all the two call
shapes need.

## Failure isolation and retries

Both review graphs carry a `failures` key alongside `reviews`, holding `ItemFailure` records
(repository, number, stage, error type, error message). Every node writes to it, so its
channel reducer concatenates instead of clobbering, while `reviews` and the fetch output are
last-write-wins.

Each unit of work is isolated. `fetch_*` catches per repository — a GitHub error on one of
thirty is recorded (`number` 0, since there's no item) and the scan moves to the next — and
again per item inside it. `review_*` catches per item, so a model error on the fifth pull
request of ten still leaves the other nine reviewed and posted. `post_review_comments`
catches per comment. In every case the failure is logged at `WARNING`, appended to
`failures`, and the loop continues. `collectFailures` in `agents/shared.ts` does both; it
takes the work as a callback and returns whether it succeeded, so a caller that needs to
branch on the outcome can.

Every node is registered with `retryPolicy: { maxAttempts: 3 }`, node-granular, so with the
per-item handling above it's a backstop for errors escaping a loop rather than a per-review
retry. Transient per-call backoff (`Retry-After`, 5xx) belongs in the clients, and true
per-item retry needs `Send` fan-out — both in [`TODO.md`](../TODO.md).

A run that recorded any failure exits non-zero; see [`USAGE.md`](../USAGE.md).

## Known gaps

The three graphs are linear and sequential — [`TODO.md`](../TODO.md) lists what that leaves
on the table: no `Send` fan-out, so ten PRs mean thirty serial model calls (three lenses
each) with no per-item retry; no checkpointer on the review graphs, so a crash mid-run loses
everything; no streaming in the chat REPL. The chat agent still returns an unvalidated
`string` — only the two review agents go through a schema.
