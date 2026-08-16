# Logs

Every run logs to two places at once, configured in `src/nishikihebi/logs.py` by
`configure_logging()`, which `__main__.main()` calls before anything else happens.

| Destination | Level | Format |
|---|---|---|
| Console (stderr) | `INFO` | `LEVEL   message` — high-level progress, meant to be read while it runs. `ColorFormatter` colors the level name only (`DEBUG` dim, `INFO` cyan, `WARNING` yellow, `ERROR` red, `CRITICAL` bold red); padding is computed on the plain name, so the columns line up either way. Color follows the same `NISHIKIHEBI_COLOR` / `NO_COLOR` rules as the rest of the console — see [`USAGE.md`](USAGE.md#color) |
| `log/nishikihebi-<timestamp>.jsonl` | `DEBUG` | one JSON object per line, carrying every structured field the nodes attach |

The file is the detailed one: it keeps the `DEBUG` records the console drops, which is where
the per-repository and per-item detail lives — what was scanned, what was selected for
review and why, diff sizes, prompt message counts, and what each model call cost in tokens and
milliseconds.

## Record shape

Each line is a single JSON object. Four keys are always present, and the `context` dict a
call site attaches is merged in at the top level alongside them:

| Key | Meaning |
|---|---|
| `time` | UTC ISO-8601 timestamp |
| `level` | `DEBUG`, `INFO`, … |
| `logger` | the module that emitted it — e.g. `nishikihebi.agents.pr_review.nodes` |
| `message` | the human-readable message |
| …rest | whatever the call site put in `extra={"context": {...}}` |

```json
{"time": "2026-08-15T09:24:43.602447+00:00", "level": "INFO", "logger": "nishikihebi.__main__", "message": "running chat", "command": "chat", "log_path": "log/nishikihebi-20260815T092443Z.jsonl"}
{"time": "2026-08-15T09:24:43.604300+00:00", "level": "DEBUG", "logger": "nishikihebi.agents.chat.graph", "message": "wiring call_llm node"}
{"time": "2026-08-15T09:24:43.605278+00:00", "level": "INFO", "logger": "nishikihebi.agents.chat.graph", "message": "chat graph ready"}
```

## How call sites log

Call sites do not touch `logging` directly. `nishikihebi.logs.get_logger()` returns a
`ContextLogger` whose `debug` / `info` / `warning` / `error` take the structured fields as
keyword arguments and pack them into the `context` dict for you:

```python
from nishikihebi.logs import get_logger

log = get_logger(__name__)

log.debug(
    "evaluated pull request",
    repository=pull_request.repository,
    number=pull_request.number,
    selected=selected,
    reason=reason,
)
```

The stdlib logger is still underneath — `ContextLogger.logger` reaches it — so the record
that lands in the file is exactly the one an `extra={"context": {...}}` call would have
produced, `logger` name included.

### Failure records write themselves

The five failure sites all log the same five keys and then append a matching `ItemFailure`
to graph state. `nishikihebi.agents._shared.collect_failures()` is a context manager that
does both, so the node body holds the work rather than the bookkeeping:

```python
with collect_failures(
    failures,
    "failed to review pull request",
    stage="review_pull_requests",
    repository=pull_request.repository,
    number=pull_request.number,
):
    ...
    reviews.append(Review(pull_request, body))
```

It catches `Exception` (never `BaseException`), logs the `WARNING` described under
[Failure records](#failure-records), appends the `ItemFailure`, and suppresses the error so
the loop continues. Work on the success path goes inside the `with` body. Where that is not
possible, the yielded scope carries a `.failed` flag to branch on.

`log_review_produced()` in the same module owns the `review produced` record, including the
`severity_counts` tally — which is why that arithmetic no longer appears in the review nodes.
It takes the calling module's `log`, so the record still names the node that produced it.

Because every line is self-contained JSON, `jq` is the natural way to read a run:

```bash
jq -r 'select(.level == "INFO") | .message' log/nishikihebi-*.jsonl
jq 'select(.selected == false) | {repository, number, reason}' log/nishikihebi-*.jsonl
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
jq 'select(.finding_count) | {repository, number, finding_count, severity_counts}' log/nishikihebi-*.jsonl
```

A reply the schema rejects never reaches this record; it is caught per item and logged as a
failure below, with `error_type` naming the validation error.

## Model call records

Every call into the model logs one `DEBUG` record from `nishikihebi.clients.llm`, message
`model call completed`, so a run's token spend and latency are recoverable after the fact:

| Key | Meaning |
|---|---|
| `call` | `complete` or `complete_structured` — which client method made it |
| `schema` | the schema the reply had to match; only on `complete_structured` |
| `finish_reason` | what the provider said ended the reply — `stop`, `length`, `None` if absent |
| `input_tokens` / `output_tokens` / `total_tokens` | from the reply's `usage_metadata`; all three are `null` when the provider returns none |
| `duration_ms` | wall time around the provider call, milliseconds |

The record is written before the truncation check, so a call that hits the
`max_completion_tokens` ceiling is still accounted for — it shows up as `finish_reason:
"length"` next to the `WARNING` for the item it cost. A call that raises before returning
logs nothing here; it is the failure record that names it.

```bash
jq -s 'map(select(.message == "model call completed") | .total_tokens // 0) | add' log/nishikihebi-*.jsonl
jq 'select(.message == "model call completed") | {call, schema, total_tokens, duration_ms}' log/nishikihebi-*.jsonl
```

### The run total on the console

`log_model_call_completed` also accumulates these four fields into a per-run tally in
`clients/llm.py`, which `__main__` prints as the `Usage` section when the run ends — the
same numbers the first `jq` above recovers, without needing the log:

| Function | Purpose |
|---|---|
| `usage_totals()` | a snapshot of `calls`, `input_tokens`, `output_tokens`, `total_tokens`, `duration_ms`; later calls do not mutate a snapshot already taken |
| `reset_usage()` | zeroes the tally; `main()` calls it once before the command runs |

A call whose reply carries no `usage_metadata` still increments `calls` and `duration_ms`,
so the call count on the console always matches the number of `model call completed`
records in the log. The section's layout is in [`USAGE.md`](USAGE.md#the-usage-section).

Dollars are not logged — see the token and cost accounting item in [`TODO.md`](TODO.md).

## Dry-run records

A `--dry-run` run logs each write it suppressed, at `INFO`, from
`nishikihebi.clients.github`. Both records carry `dry_run: true`, so one filter shows
everything the run would have written:

| Message | Context keys |
|---|---|
| `dry run: skipping ensure_label` | `dry_run`, `repository`, `label` |
| `dry run: skipping post_comment` | `dry_run`, `repository`, `number`, `body_length` |

```bash
jq 'select(.dry_run == true) | {message, repository, number}' log/nishikihebi-*.jsonl
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
| `error_type` | the exception class name |
| `error` | `str(exception)` |

```bash
jq 'select(.level == "WARNING") | {stage, repository, number, error_type, error}' log/nishikihebi-*.jsonl
```

These are the same records the run collects into `failures` in graph state and reports
before exiting non-zero. No traceback is logged — `JsonLinesFormatter` drops `exc_info`,
which is why the exception type and message are structured fields instead.

## Where the files go

`configure_logging()` writes to `log/` **relative to the current working directory**, so
where logs land depends on where you invoked the command from. One file per run, named for
the UTC start time. `log/` is gitignored.

## Known gaps

Logging is not production-shaped yet, and [`TODO.md`](TODO.md) tracks the specifics:

- **"Log JSON to stdout by default"** — logging is file-first with no rotation and no
  retention, one file per run, and the path depends on cwd. The 12-factor answer is JSON to
  stdout with the file handler behind an opt-in flag. Also missing: a run-id to group one
  run's lines, and `exc_info` capture — nothing currently logs a traceback.
- Under that same item — `log_review_produced()` logs the **entire rendered review body** at
  `DEBUG`, so model output derived from untrusted input lands on disk unbounded. Both review
  nodes now share that one helper, so capping the body is a change in a single place.
  Combined with no retention, that is a slow disk-fill and a data-handling question.
- Nothing redacts secrets; the formatter dumps whatever is in `context`.
