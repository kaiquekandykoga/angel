---
name: make-plan
description: >
  Turn an instruction into an implementation plan, hand the tasks off to the appropriate agents, then commit and push. Use when the user says "make plan", "plan this", or asks for a plan to be built and carried out
model: opus
effort: high
---

# Make plan
Plan the requested work, delegate each task to the right agent, then ship it

The instruction to plan is whatever the user passed to this skill (or their preceding message).

## Steps
1. Scope: restate the request in one line. Read only the lines needed to plan it (`Grep`, specific line ranges — never whole trees). `docs/GRAPHS.md` maps the three graphs to files and is usually faster than reading `src/`. Spawn `Explore` only when the relevant code cannot be located in two or three targeted searches.
2. Plan: write a numbered, ordered task list. Each task states the behavior, the files it touches, and how it is verified. Delegate to the `Plan` agent only for genuine architectural trade-offs.
3. Confirm: show the plan and get approval before any code changes. Use `AskUserQuestion` only when a real ambiguity would change the plan.
4. Delegate: one task per agent invocation, each carrying its files and acceptance criteria so the agent needs no discovery of its own.
   - Python behavior under `src/nishikihebi/` and `tests/` → `python-engineer` (strict TDD; it runs its own suite)
   - Docs, `.env.example`, `pyproject.toml`, `.claude/` → do it inline; these have no tests to drive
   Run independent tasks in parallel; run dependent tasks in order, passing the previous result forward. Do the work inline when it is smaller than the handoff.

   A behavior change usually drags a doc with it — plan the doc edit as its own task, do not leave it to the engineer agent:
   - new or renamed `NISHIKIHEBI_*` variable, or a change to a command's arguments → `.env.example` and `docs/USAGE.md`
   - node added, removed, or rewired in a graph → the affected diagram and node walkthrough in `docs/GRAPHS.md`
   - change to console output or the JSONL record written to `log/` → `docs/LOGS.md`
   - work that closes something in `docs/TODO.md` → delete that item (git history is the record; the file has no "Done" section); new work discovered along the way → add an item using the template at the top of that file
   - new agent package `src/nishikihebi/agents/<name>/` → mirrored `tests/agents/<name>/`
5. Ship: take each agent's report at face value, then run `uv run ci` (ruff → basedpyright → pytest) once over the whole tree — that green is the merge signal, not GitHub Actions. Then run `/commit-and-push-changes`.
6. Minimal report: tasks completed, `uv run ci` result, PR URL.
