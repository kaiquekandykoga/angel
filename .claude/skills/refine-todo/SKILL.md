---
name: refine-todo
description: >
  Read the app, then bring docs/TODO.md back in line with it — correct or re-prioritize existing items, retire landed ones, and add new work. Use when the user says "refine todo", "refine the todos", "update the backlog", or asks for new backlog items
model: opus
effort: high
---

# Refine todo
Make `docs/TODO.md` true again: fix what drifted, retire what landed, add what's missing

If the user passed a scope (a file, a directory, a theme like "logging" or "security"), refine only the items and code in that scope. With no scope, sweep the whole app.

## Steps
1. Load the backlog first: read `docs/TODO.md` end to end. Every existing item is now something to re-check, not just a duplicate filter. Do this before reading any code.
2. Read the code. Prefer whole files over greps here: this skill is looking for what is *missing*, and absence does not grep. Budget for the sweep:
   - `src/nishikihebi/clients/github.py`, `clients/llm.py` — the network boundary; where errors, limits, and untrusted data enter
   - `src/nishikihebi/agents/*/nodes.py`, `graph.py`, `prompts.py` — the graphs; where model output becomes a public comment
   - `src/nishikihebi/__main__.py`, `settings.py`, `env.py`, `logs.py`, `__ci__.py` — the operational surface
   - `tests/` — what plumbing is asserted, and what behavior is asserted nowhere
   - `pyproject.toml`, `.env.example`, `docs/` — packaging, configuration, and docs that have drifted from the code
   Spawn `Explore` agents only when a sweep is too wide to hold in one pass; do the reading inline otherwise.
3. Re-check every existing item against what you just read. The file's own rule applies: **verify before editing, read the code, don't trust this file's line numbers or claims.** Each item lands in one of:
   - **Still true, still accurate** — leave it exactly as it is. Most items should end here; churn on wording is not refinement.
   - **Drifted** — line numbers moved, a path was renamed, or the *Why* describes code that has since changed shape. Correct the item in place, keeping it short.
   - **Mis-prioritized** — promote when reality changed (anything becomes P0 the moment it causes wrong behavior in a real run); demote only when the risk it names has actually gone away.
   - **Oversized** — one item that needs two PRs is two items. Split it, giving each its own *Done when*.
   - **Landed** — delete it. Only when its *Done when* condition genuinely holds in the code **and** `uv run ci` is green; run it yourself before deleting anything. The file keeps no "Done" section — git history is the record. If it is partly done, shrink the item to what remains instead of deleting it.
   - **Obsolete** — the gap no longer exists because the design moved, not because the work was done. Delete it and say so in your report.
4. Find new work. A candidate is an item only if it names a **concrete failure or gap — a symptom, not a preference**. Test it with "what breaks, and when?". Drop anything answered with "it would be nicer if". Sources that reliably produce real items:
   - a code path that fails on input the app will actually see (large, paginated, malformed, hostile, rate-limited)
   - a LangGraph capability the app should be using and is not (checkpointers, `Send`, structured output, `interrupt`, `RetryPolicy`)
   - a Python/tooling practice not yet adopted (stricter ruff/basedpyright, `pydantic-settings`, audit tooling)
   - an operational gap (no metric, no alert, no way to deploy, no way to debug a bad run)
   - a doc or config that now contradicts the code
5. Verify each new candidate against the source before writing it. Quote nothing from memory: open the file, confirm the line, confirm the claim still holds. An item built on a stale line number or a misread is worse than no item.
6. Write the changes into `docs/TODO.md`. New items go under their priority heading (P0/P1/P2 — the table in that file defines them), using the exact template at the top of the file: `**Where:**`, `**Why:**`, `**Do:**`, `**Done when:**`. Keep every item short — rationale that isn't actionable belongs in `docs/`, not here. Code sketch only when the shape is non-obvious.
7. Report, grouped: items added (title + priority), items corrected or re-prioritized (with what changed), items retired (with the evidence that closed them), and one line naming what you examined and rejected, so the next run doesn't re-litigate it.

Quality beats count. Three verified changes are a good run; ten speculative ones make the file dishonest. If the sweep finds the file already accurate, say so and change nothing.
