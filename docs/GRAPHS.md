# Graphs

Each command is a [LangGraph](https://langchain-ai.github.io/langgraphjs/) state graph, and
each one owns a directory under `src/agents/` — `agents/chat/`,
`agents/pr-review/`, `agents/issue-review/`. Inside each, `graph.ts` wires the nodes,
`state.ts` declares the state threaded between them, `prompts.ts` holds the system prompt,
and `nodes.ts` holds the nodes themselves: factories that take their dependencies (LLM
client, GitHub client) and return the node function, so a graph can be built against fakes
in tests. Anything two agents share — the `Review` record, the `ItemFailure` record, the
`postReviewComments` node, the comment helpers, and the review output schemas and their
markdown renderers — lives in `agents/shared.ts`. Those dependencies sit behind
interface seams in `src/clients/`, and the reviewer login, label, and label
colour in `src/settings.ts`.

Both review agents ask the model for a schema, not prose: `LlmClient.completeStructured`
binds the OpenAI-style `response_format` json_schema for `PullRequestReviewOutput` /
`IssueReviewOutput` and validates the reply against that [zod](https://zod.dev) schema
itself, rather than going through LangChain's `withStructuredOutput` — whose fallback chain
retries a truncated reply with `guided_json`, a format the hosted endpoint rejects, so a
truncation surfaced as a misleading `400 unknown field guided_json`. A completion stopped by
the token ceiling raises `TruncatedCompletionError`, and a reply that does not fit the schema
raises a zod validation error; either way the pull request is recorded as an item failure
instead of being posted. The comment body is rendered from the validated object —
`pr_review` merges its three lens objects into one body in `agents/pr-review/nodes.ts`,
`issue_review` renders its single object with `renderIssueReview`.

The endpoint is OpenAI-compatible, so the model is a `ChatOpenAI` from
`@langchain/openai` pointed at `https://integrate.api.nvidia.com/v1`; the client seam in
`clients/llm.ts` is one `invoke(messages, options)` method, which is all the two call
shapes need.

## `chat`

An interactive assistant REPL over a one-node graph. `agents/chat/repl.ts` reads a line at
a time and stops at `/exit` or end of input (Ctrl-D), and holds the `threadId`
generated when the session starts, invoking the graph once per line. The conversation
grows because the state uses LangGraph's `MessagesAnnotation` — the `addMessages` reducer —
and the compiled graph carries a checkpointer (`MemorySaver` by default), so each
invocation appends to that same thread — and the history lives only in memory, so it ends
with the process.

```
  START
    |
    v
  +----------+
  | call_llm |  <--- NVIDIA model: system prompt + conversation so far
  +----------+
    |  reply appended to state.messages
    v
   END
```

`call_llm` prepends the system prompt to the accumulated messages, calls the model, and
returns the reply for the reducer to append.

## `pr_review`

Reviews open pull requests across every repository the App installation can reach — the
set is discovered at run time from GitHub, so granting or revoking the App's access to a
repository is all it takes to add or drop it. Only PRs labeled `angel` are
considered; the label is created on each repository if it doesn't already exist. A
labeled pull request is picked up when `kandy-angel[bot]` has never commented on
it, or when its current head sha differs from the one recorded in that last comment —
each review ends with a `<!-- angel: sha=… -->` marker naming the head it read, so
a PR is re-reviewed exactly when its head has moved.

```
  START
    |
    v
  +---------------------+
  | fetch_pull_requests |  <--- GitHub: installation repositories,
  +---------------------+       ensures the `angel` label exists,
    |                           then their open PRs labeled `angel` + comments
    |  PullRequestContext (pull request + comments), only the ones due for review
    v
  +----------------------+
  | review_pull_requests |  <--- GitHub: the PR diff
  +----------------------+  <--- NVIDIA model, once per lens (security, quality,
    |                             performance): a PullRequestReviewOutput each
    |  Review (target + body)
    v
  +----------------------+
  | post_review_comments |  ---> GitHub: comment posted on the PR
  +----------------------+
    |
    v
   END
```

| Node | Does |
|---|---|
| `fetch_pull_requests` | Ensures each repository has the `angel` label, lists PRs carrying it and their comments, keeps the ones due for review, and emits `PullRequestContext` (the PR plus its comments) |
| `review_pull_requests` | Fetches the diff, then asks the model for a `PullRequestReviewOutput` (summary + severity-tagged findings) three times over the same title, description, existing comments, and diff — once per specialised lens (security, quality, performance), each prompted to stay in its lane — and merges the three into one comment body with a finding section per lens. A lens that fails fails the whole pull request: nothing is posted and it is retried next run |
| `post_review_comments` | Posts each review as an issue comment on its PR |

Under `--dry-run` the wiring is identical — the flag wraps the GitHub client in a read-only
`DryRunGitHubClient`, so the label check in `fetch_pull_requests` and the comment in
`post_review_comments` become logged no-ops while every read behaves as usual. See
[`USAGE.md`](USAGE.md).

## `issue_review`

Same shape as `pr_review`, over the open issues of the same discovered repositories. Only
issues labeled `angel` are considered; the label is created on each repository if
it doesn't already exist. A labeled issue is picked up when `kandy-angel[bot]` has
never commented on it, or when the issue's `updatedAt` is newer than that last comment —
which covers both an edited description and new comments.

```
  START
    |
    v
  +--------------+
  | fetch_issues |  <--- GitHub: installation repositories,
  +--------------+       ensures the `angel` label exists,
    |                    then their open issues labeled `angel` + comments
    |  IssueContext (issue + comments), only the ones due for review
    v
  +---------------+
  | review_issues |  <--- NVIDIA model: an IssueReviewOutput
  +---------------+
    |  Review (target + body)
    v
  +----------------------+
  | post_review_comments |  ---> GitHub: comment posted on the issue
  +----------------------+
    |
    v
   END
```

| Node | Does |
|---|---|
| `fetch_issues` | Ensures each repository has the `angel` label, lists issues carrying it and their comments, keeps the ones due for review, and emits `IssueContext` (the issue plus its comments) |
| `review_issues` | Asks the model for an `IssueReviewOutput` (summary, findings, acceptance criteria, suggested approach) given the title, description, and existing comments, then renders it to the comment body |
| `post_review_comments` | Shared with `pr_review` — posts each review as an issue comment |

`--dry-run` applies here too, by the same wrapper.

## Failure isolation and retries

Both review graphs carry a `failures` key alongside `reviews`, holding `ItemFailure`
records (repository, number, stage, error type, error message). Every node writes to it, so
its channel reducer concatenates instead of clobbering, while `reviews` and the fetch output
are last-write-wins.

Each unit of work is isolated. `fetch_*` catches per repository — a GitHub error on one
repository of thirty is recorded (with `number` 0, since there is no item) and the scan
moves to the next — and again per item inside it. `review_*` catches per item, so a model
error on the fifth pull request of ten still leaves the other nine reviewed and posted.
`post_review_comments` catches per comment. In every case the failure is logged at
`WARNING`, appended to `failures`, and the loop continues. `collectFailures` in
`agents/shared.ts` is the one helper that does both; it takes the work as a callback and
returns whether it succeeded, so a caller that needs to branch on the outcome can.

Every node is registered with `retryPolicy: { maxAttempts: 3 }`. That policy is
node-granular, so with the per-item handling above it acts as a backstop for errors that
escape a loop rather than as a per-review retry. Transient per-call backoff (`Retry-After`,
5xx) belongs in the clients, and true per-item retry needs `Send` fan-out — both are in
[`TODO.md`](TODO.md).

A run that recorded any failure exits non-zero; see [`USAGE.md`](USAGE.md).

## Known gaps

The three graphs are linear and sequential, and [`TODO.md`](TODO.md) lists what that leaves
on the table: no `Send` fan-out, so ten PRs mean thirty serial model calls — three lenses each —
and no per-item retry; no checkpointer on the review graphs, so a crash mid-run loses everything; and no
streaming in the chat REPL. The chat agent still returns an unvalidated `string` — only the two
review agents go through a schema.
