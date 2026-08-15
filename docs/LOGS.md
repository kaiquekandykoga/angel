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

## Where the files go

`configure_logging()` writes to `log/` **relative to the current working directory**, so
where logs land depends on where you invoked the command from. One file per run, named for
the UTC start time. `log/` is gitignored.

## Known gaps

Logging is not production-shaped yet, and [`TODO.md`](TODO.md) tracks the specifics:

- **§8.3** — file-first with no rotation and no retention, one file per run, and the path
  depends on cwd. The 12-factor answer is JSON to stdout with the file handler behind an
  opt-in flag. Also missing: a run-id to group one run's lines, and `exc_info` capture —
  nothing currently logs a traceback.
- **§5.3** — `review_issues` / `review_pull_requests` log the **entire review body** at
  `DEBUG`, so model output derived from untrusted input lands on disk unbounded. Combined
  with no retention, that is a slow disk-fill and a data-handling question.
- **§5.2** — nothing redacts secrets; the formatter dumps whatever is in `context`.
