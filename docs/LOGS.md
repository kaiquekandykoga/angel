# Logs

Every run logs to two places at once, configured in `src/logs.ts` by
`configureLogging()`, which `main()` calls before anything else happens.

| Destination | Level | Format |
|---|---|---|
| Console (stderr) | `INFO` | `LEVEL   message` — high-level progress, meant to be read while it runs. The console handler colors the level name only (`DEBUG` dim, `INFO` cyan, `WARNING` yellow, `ERROR` red, `CRITICAL` bold red); padding is computed on the plain name, so the columns line up either way. Color follows the same `ANGEL_COLOR` / `NO_COLOR` rules as the rest of the console — see [`USAGE.md`](USAGE.md#color) |
| `log/angel-<timestamp>.jsonl` | `DEBUG` | one JSON object per line, carrying every structured field the nodes attach |

The file is the detailed one: it keeps the `DEBUG` records the console drops, which is where
the per-repository and per-item detail lives — what was scanned, what was selected for
review and why, diff sizes, prompt message counts, and what each model call cost in tokens and
milliseconds.

## Record shape

Each line is a single JSON object. Four keys are always present, and the context object a
call site attaches is merged in at the top level alongside them:

| Key | Meaning |
|---|---|
| `time` | UTC ISO-8601 timestamp |
| `level` | `DEBUG`, `INFO`, … |
| `logger` | the module that emitted it — e.g. `angel.agents.pr-review.nodes` |
| `message` | the human-readable message |
| …rest | whatever the call site passed as the context object |

```json
{"time": "2026-08-15T09:24:43.602Z", "level": "INFO", "logger": "angel.main", "message": "running chat", "command": "chat", "log_path": "log/angel-20260815T092443Z.jsonl", "dry_run": false}
{"time": "2026-08-15T09:24:43.604Z", "level": "DEBUG", "logger": "angel.agents.chat.graph", "message": "wiring call_llm node"}
{"time": "2026-08-15T09:24:43.605Z", "level": "INFO", "logger": "angel.agents.chat.graph", "message": "chat graph ready"}
```

## How call sites log

`logs.ts` exports `getLogger(name)`, which returns a `ContextLogger` whose `debug` / `info` /
`warning` / `error` take the message and an object of structured fields:

```ts
import { getLogger } from "../../logs.js";

const log = getLogger("angel.agents.pr-review.nodes");

log.debug("evaluated pull request", {
  repository: pullRequest.repository,
  number: pullRequest.number,
  selected,
  reason,
});
```

Field names in the context object are `snake_case`, so a run's log reads the same whichever
module wrote it, and `jq` filters do not have to know which one did.

Handlers are module state: `configureLogging()` installs the console and file handlers and
returns the file path, and a process that never calls it drops records rather than failing.
Tests install a capturing handler instead — see [`TESTING.md`](TESTING.md).

### Failure records write themselves

The five failure sites all log the same five keys and then append a matching `ItemFailure`
to graph state. `collectFailures()` in `src/agents/shared.ts` does both, so the node body
holds the work rather than the bookkeeping:

```ts
await collectFailures(
  failures,
  "failed to review pull request",
  {
    stage: "review_pull_requests",
    repository: pullRequest.repository,
    number: pullRequest.number,
  },
  async () => {
    // ...
    reviews.push({ target: pullRequest, body });
  },
);
```

It catches whatever the callback throws, logs the `WARNING` described under
[Failure records](#failure-records), appends the `ItemFailure`, and swallows the error so
the loop continues. Work on the success path goes inside the callback. Where a caller needs
to branch on the outcome, `collectFailures` returns `false` when it caught something.

`logReviewProduced()` in the same module owns the `review produced` record, including the
`severity_counts` tally — which is why that arithmetic no longer appears in the review nodes.
It takes the calling module's `log`, so the record still names the node that produced it.

Because every line is self-contained JSON, `jq` is the natural way to read a run:

```bash
jq -r 'select(.level == "INFO") | .message' log/angel-*.jsonl
jq 'select(.selected == false) | {repository, number, reason}' log/angel-*.jsonl
```

The second one answers "why didn't it review this PR?" — `fetch_pull_requests` and
`fetch_issues` log a `selected` / `reason` pair for every labeled item they evaluate.

## Review records

Because the model returns a schema rather than prose, `review_pull_requests` /
`review_issues` log what the review contained. The `review produced` `DEBUG` record carries
`repository`, `number`, the rendered `review` body, and:

| Key | Meaning |
|---|---|
| `finding_count` | how many findings the model returned — `0` is a clean review |
| `severity_counts` | `{"blocker": 1, "nit": 2}` — only severities actually present |
| `lens` | `security`, `quality`, or `performance` — which specialised prompt produced this record. `review_pull_requests` emits one record per lens per PR; `review_issues` makes a single call and omits the key |

```bash
jq 'select(.finding_count) | {repository, number, finding_count, severity_counts}' log/angel-*.jsonl
```

A reply the schema rejects never reaches this record; it is caught per item and logged as a
failure below, with `error_type` naming the validation error.

## Model call records

Every call into the model logs one `DEBUG` record from `angel.clients.llm`, message
`model call completed`, so a run's token spend and latency are recoverable after the fact:

| Key | Meaning |
|---|---|
| `call` | `complete` or `complete_structured` — which client method made it |
| `schema` | the schema the reply had to match; only on `complete_structured` |
| `finish_reason` | what the provider said ended the reply — `stop`, `length`, `null` if absent |
| `input_tokens` / `output_tokens` / `total_tokens` | from the reply's `usage_metadata`; all three are `null` when the provider returns none |
| `duration_ms` | wall time around the provider call, milliseconds |

The record is written before the truncation check, so a call that hits the
`maxCompletionTokens` ceiling is still accounted for — it shows up as `finish_reason:
"length"` next to the `WARNING` for the item it cost. A call that throws before returning
logs nothing here; it is the failure record that names it.

```bash
jq -s 'map(select(.message == "model call completed") | .total_tokens // 0) | add' log/angel-*.jsonl
jq 'select(.message == "model call completed") | {call, schema, total_tokens, duration_ms}' log/angel-*.jsonl
```

### The run total on the console

`logModelCallCompleted` also accumulates these four fields into a per-run tally in
`clients/llm.ts`, which `main` prints as the `Usage` section when the run ends — the
same numbers the first `jq` above recovers, without needing the log:

| Function | Purpose |
|---|---|
| `usageTotals()` | a snapshot of `calls`, `inputTokens`, `outputTokens`, `totalTokens`, `durationMs`; later calls do not mutate a snapshot already taken |
| `resetUsage()` | zeroes the tally; `main()` calls it once before the command runs |

A call whose reply carries no `usage_metadata` still increments `calls` and `durationMs`,
so the call count on the console always matches the number of `model call completed`
records in the log. The section's layout is in [`USAGE.md`](USAGE.md#the-usage-section).

Dollars are not logged — see the token and cost accounting item in [`TODO.md`](TODO.md).

## Dry-run records

A `--dry-run` run logs each write it suppressed, at `INFO`, from
`angel.clients.github`. Both records carry `dry_run: true`, so one filter shows
everything the run would have written:

| Message | Context keys |
|---|---|
| `dry run: skipping ensure_label` | `dry_run`, `repository`, `label` |
| `dry run: skipping post_comment` | `dry_run`, `repository`, `number`, `body_length` |

```bash
jq 'select(.dry_run == true) | {message, repository, number}' log/angel-*.jsonl
```

The review bodies themselves go to stdout, not the log — see [`USAGE.md`](USAGE.md).

## Failure records

Every isolated failure — a repository or item skipped while fetching, a review the model
failed to produce, a comment that could not be posted — is logged at `WARNING` with a
fixed set of context keys, so failures across all three nodes read the same way:

| Key | Meaning |
|---|---|
| `repository` | `owner/name` of the repository the failure belongs to |
| `number` | the PR or issue number; `0` for a repository-level failure |
| `stage` | the node that caught it — `fetch_pull_requests`, `fetch_issues`, `review_pull_requests`, `review_issues`, `post_review_comments` |
| `error_type` | the error's `name` — `HttpStatusError`, `TruncatedCompletionError`, `TypeError`, … — or the `typeof` for a thrown non-error |
| `error` | the error's `message` |

```bash
jq 'select(.level == "WARNING") | {stage, repository, number, error_type, error}' log/angel-*.jsonl
```

These are the same records the run collects into `failures` in graph state and reports
before exiting non-zero. No stack trace is logged — the JSON handler writes only the four
fixed keys and the context, which is why the error type and message are structured fields
instead.

## Where the files go

`configureLogging()` writes to `log/` **relative to the current working directory**, so
where logs land depends on where you invoked the command from. One file per run, named for
the UTC start time. `log/` is gitignored.

## Known gaps

Logging is not production-shaped yet, and [`TODO.md`](TODO.md) tracks the specifics:

- **"Log JSON to stdout by default"** — logging is file-first with no rotation and no
  retention, one file per run, and the path depends on cwd. The 12-factor answer is JSON to
  stdout with the file handler behind an opt-in flag. Also missing: a run-id to group one
  run's lines, and stack-trace capture — nothing currently logs one.
- Under that same item — `logReviewProduced()` logs the **entire rendered review body** at
  `DEBUG`, so model output derived from untrusted input lands on disk unbounded. Both review
  nodes now share that one helper, so capping the body is a change in a single place.
  Combined with no retention, that is a slow disk-fill and a data-handling question.
- Writes are synchronous `appendFileSync` calls, one per record — fine for a short CLI run,
  wrong for anything long-lived.
- Nothing redacts secrets; the handler serialises whatever is in the context object.
