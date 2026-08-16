---
name: refine-todo
description: >
  Sweep the app for production-readiness gaps — logging, security, reliability, performance, cost, readability — and bring docs/TODO.md back in line: correct drifted items, retire landed ones, add verified new work. Takes no arguments. Use when the user says "refine todo", "refine the todos", "update the backlog", or asks for new backlog items
model: opus
effort: high
---

# Refine todo
Make `docs/TODO.md` true again: fix what drifted, retire what landed, add what's missing. No arguments — always sweep the whole app through the four lenses below.

## Lenses
Every new item must come from one of these, and name a **concrete failure — a symptom, not a preference**. Test with "what breaks, and when?"; drop anything answered by "it would be nicer if".
* **Logging/ops** — a failure that leaves no trace: unlogged exception path, missing run id or correlation, a metric or exit signal you'd need to debug a bad run, secrets or PII in log records.
* **Security** — untrusted input reaching a sink: GitHub/LLM payloads into prompts or comments, prompt injection, unvalidated config, over-broad token scope, unpinned or unaudited deps.
* **Reliability/side effects** — what the second run does: a public comment or label written twice, a crash mid-run with no checkpointer to resume from, state lost on restart (`MemorySaver`), a partial failure that takes the whole run down, an exit code that lies.
* **Performance** — a path that degrades on input the app will actually see: unpaginated or N+1 GitHub calls, unbounded context sent to the LLM, no timeout, no retry/backoff, serial work that `Send` could fan out.
* **Cost** — unbounded LLM spend: no input-token ceiling, no usage accounted per run, no prompt caching, a model tier heavier than the node needs.
* **Readability/maintainability** — a shape that makes the next change wrong: duplicated logic across nodes, a function doing two jobs, untyped or `Any`-leaking boundary, behavior asserted nowhere in `tests/`, doc or `.env.example` contradicting the code.

## Steps
1. Read `docs/TODO.md` end to end. Every existing item is now something to re-check.
2. Read code, cheapest sufficient read first — line ranges and `Grep` for verifying a specific claim, whole file only when hunting for what's *absent*. Cover, in this order, stopping once the lenses are satisfied: `clients/github.py`, `clients/llm.py` (network boundary) → `agents/*/nodes.py`, `graph.py`, `prompts.py` (model output → public comment) → `__main__.py`, `settings.py`, `env.py`, `logs.py` (operational surface) → `tests/`, `pyproject.toml`, `.env.example`, `docs/`. Do it inline; no subagents.
3. Re-check each existing item against what you read — **verify before editing; don't trust this file's line numbers or claims.** Each lands in one of:
   * **Accurate** — leave it byte-for-byte. Most items end here; wording churn is not refinement.
   * **Drifted** — line moved, path renamed, *Why* describes code that changed shape. Correct in place, keep it short.
   * **Mis-prioritized** — promote to P0 the moment it causes wrong behavior in a real run; demote only when the named risk is gone.
   * **Oversized** — needs two PRs, so it's two items, each with its own *Done when*.
   * **Landed** — delete only when its *Done when* holds in the code **and** `uv run ci` is green; run it once, before any deletions. Partly done → shrink to what remains. No "Done" section; git history is the record.
   * **Obsolete** — gap gone because the design moved, not because work happened. Delete and say so.
4. Add new work from the lenses. Verify each candidate at the source before writing it — open the file, confirm the line, confirm the claim. Cap at **five** new items; if a sixth is stronger, drop the weakest instead of appending.
5. Write into `docs/TODO.md` under the right priority heading, using that file's exact template: `**Where:**`, `**Why:**`, `**Do:**`, `**Done when:**`. Keep items short; non-actionable rationale belongs in `docs/`. Code sketch only when the shape is non-obvious.
6. Report in four lines or less, grouped: added (title + priority), corrected/re-prioritized (what changed), retired (evidence that closed them), and what you examined and rejected, so the next run doesn't re-litigate it.

Quality beats count. Three verified changes are a good run; ten speculative ones make the file dishonest. If the file is already accurate, say so and change nothing.
