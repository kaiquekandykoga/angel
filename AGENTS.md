# AGENTS.md

Maximize token efficiency — never at the cost of correctness, safety, or verification.

## Tokens
* **Zero fluff:** no plan narration before tools, no summaries or celebration after. Move tool to tool.
* **Minimal output:** brief, scannable, bullets over paragraphs.
* **Targeted context:** no speculative whole-file or tree reads; use `Grep` and line ranges.

## Quality
* **Complete code:** fewer lines via precision, never by dropping error boundaries, validation, or edge cases.
* **No comments** unless requested; delete stale ones rather than updating.
* **Verify:** run relevant tests and linters before calling a task done.
* **No ghost fixes:** report raw failures; never mask or suppress.

## This Project
* **Python is delegated** to the `python-engineer` agent (stack, uv, TDD, style in `.claude/agents/python-engineer.md`).
* **Docs sync** with behavior changes: `docs/USAGE.md` (env vars, commands), `docs/GRAPHS.md` (graph wiring), `docs/LOGS.md` (log records), `docs/TODO.md` (backlog).
* **Merge on local green:** `uv run ci` locally is the signal; don't gate on GitHub Actions.
