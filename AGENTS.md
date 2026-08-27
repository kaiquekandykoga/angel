# AGENTS.md

Maximize token efficiency — never at cost of correctness, safety, or verification.

## Tokens
* Zero fluff: no plan narration, no summaries/celebration. Tool to tool.
* Brief, scannable, bullets over paragraphs.
* No speculative whole-file/tree reads — `Grep` + line ranges.

## Quality
* Fewer lines via precision, never by dropping error boundaries, validation, or edge cases.
* No comments unless requested; delete stale ones, don't update.
* Verify: run relevant tests/linters before calling done.
* No ghost fixes — report raw failures, never mask or suppress.
* Repo is public — never commit secrets or personal data.

## This Project
* TypeScript, ESM, Node >= 22. Strict `tsc`, Biome (lint+format), Vitest, TDD.
* Docs sync with behavior: `docs/USAGE.md` (env vars, commands), `docs/LAYOUT.md` (directory tree), `docs/agents/` (graph wiring), `docs/LOGS.md` (log records), `docs/TESTING.md` (suites), `docs/TODO.md` (backlog).
* Green = `npm run ci` (`biome ci` → `tsc --noEmit` → `vitest run`); same three run in GitHub Actions on every push/PR.
