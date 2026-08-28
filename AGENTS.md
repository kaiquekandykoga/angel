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
* Green = `npm run ci` (`biome ci` → `tsc --noEmit` → `vitest run`); same three run in GitHub Actions on every push/PR.

### Map
* `apps/server/` — engine; `index.ts` is the surface. `agents/{chat,pr-review,issue-review}/{graph,state,prompts,nodes}.ts`; `agents/shared.ts` owns both review agents' scan/review loops, state channels, output schemas, renderers, failure isolation, and the untrusted-input layer (`fenceUntrusted`, `UNTRUSTED_CONTENT_POLICY`, `finalizeReviewBody` — every posted body goes through it) — change review machinery there, not twice. `agents/pr-review/diff.ts` filters and caps the diff before it reaches the model. `external/{github,nvidia}/{client,settings}.ts`; `clients/http.ts`.
* `apps/cli/` — `bin` → `main` (command → graph) → `ui` (parse + render), `repl` (chat loop).
* `packages/shared/` — `env`, `logs`, `console`. `eval/` — Langfuse harness. `tests/` mirrors all three.

### Docs sync with behavior
`docs/USAGE.md` (env vars, commands, exit codes) · `docs/INSTALL.md` (install paths) · `docs/LAYOUT.md` (directory tree) · `docs/agents/` (graph wiring) · `docs/LOGS.md` (log records) · `docs/TESTING.md` (suites, helpers) · `docs/EVAL.md` (scores, dataset) · `docs/TODO.md` (backlog)
