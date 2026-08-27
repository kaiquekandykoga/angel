# AGENTS.md

Maximize token efficiency — never at the cost of correctness, safety, or verification.

## Tokens
* **Zero fluff:** no plan narration before tools, no summaries or celebration after. Move tool to tool.
* **Minimal output:** brief, scannable, bullets over paragraphs.
* **Targeted context:** no speculative whole-file or tree reads; use `Grep` and line ranges.

## Open Source
* Repo is public — never commit secrets, credentials, or personal/sensitive data.

## Quality
* **Complete code:** fewer lines via precision, never by dropping error boundaries, validation, or edge cases.
* **No comments** unless requested; delete stale ones rather than updating.
* **Verify:** run relevant tests and linters before calling a task done.
* **No ghost fixes:** report raw failures; never mask or suppress.

## This Project
* **TypeScript, ESM, Node >= 22.** Strict `tsc`, Biome for lint and format, Vitest for tests, TDD.
* **Docs sync** with behavior changes: `docs/USAGE.md` (env vars, commands), `docs/GRAPHS.md` (graph wiring), `docs/LOGS.md` (log records), `docs/TESTING.md` (suites), `docs/TODO.md` (backlog).
* **Green means `npm run ci`** — `biome ci`, then `tsc --noEmit`, then `vitest run`. The same three run in GitHub Actions on every push and pull request.
