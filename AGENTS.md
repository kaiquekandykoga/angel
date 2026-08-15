# AGENTS.md

## Core Directive: Extreme Token Efficiency
Maximize cost efficiency across all LLM operations. Cost optimization must never compromise correctness, safety, or comprehensive verification.

## 1. Token Constraints
* **Zero Fluff:** Do not narrate plans before tool calls. Do not summarize or celebrate after successes. Transition directly between tools.
* **Minimalist Output:** Keep final responses brief, scannable, and direct. Prioritize bullet points over paragraphs.
* **Targeted Context:** Do not read whole files or directory trees speculatively. Use precise tools (`Grep`, specific line ranges) to minimize input tokens.

## 2. Quality & Execution
* **Complete Code:** Write fewer lines of code by being precise, not by skipping error boundaries, input validation, or edge cases.
* **No Comments:** No comments unless explicitly requested. This applies to new code and to code you touch: delete a stale comment rather than updating it.
* **Strict Verification:** Never assume success. Run relevant test suites and linters before marking a task complete.
* **No Ghost Fixes:** Report raw failures honestly. Fix errors directly; never mask or suppress them to save output tokens.

## 3. This Project
* **Python Work Is Delegated:** All Python changes go to the `python-engineer` agent. Its stack, uv commands, dependency rules, TDD cycle, test hermeticity, and code style live in `.claude/agents/python-engineer.md`.
* **Docs Stay In Sync:** Behavior changes update the matching doc — `docs/USAGE.md` (env vars, commands), `docs/GRAPHS.md` (graph wiring), `docs/LOGS.md` (log records), `docs/TODO.md` (backlog).
* **Merge On Local Green:** `uv run ci` passing locally is the merge signal; do not gate on GitHub Actions.
