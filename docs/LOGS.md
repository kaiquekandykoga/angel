# Logs

Every run logs to two places at once, configured in `src/nishikihebi/logs.py` by
`configure_logging()`, which `__main__.main()` calls before anything else happens.

| Destination | Level | Format |
|---|---|---|
| Console (stderr) | `INFO` | `LEVEL   message` — high-level progress, meant to be read while it runs |
| `log/nishikihebi-<timestamp>.jsonl` | `DEBUG` | one JSON object per line, carrying every structured field the nodes attach |

The file is the detailed one: it keeps the `DEBUG` records the console drops, which is where
the per-repository and per-item detail lives — what was scanned, what was selected for
review and why, diff sizes, prompt message counts.

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

Because every line is self-contained JSON, `jq` is the natural way to read a run:

```bash
jq -r 'select(.level == "INFO") | .message' log/nishikihebi-*.jsonl
jq 'select(.selected == false) | {repository, number, reason}' log/nishikihebi-*.jsonl
```

The second one answers "why didn't it review this PR?" — `fetch_pull_requests` and
`fetch_issues` log a `selected` / `reason` pair for every labeled item they evaluate.

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
- Under that same item — `review_issues` / `review_pull_requests` log the **entire review
  body** at `DEBUG`, so model output derived from untrusted input lands on disk unbounded.
  Combined with no retention, that is a slow disk-fill and a data-handling question.
- Nothing redacts secrets; the formatter dumps whatever is in `context`.
