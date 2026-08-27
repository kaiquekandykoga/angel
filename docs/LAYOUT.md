# Layout

```
apps/server/    the LangGraph engine — agents, external integrations, HTTP; `index.ts` is its surface
apps/cli/       the terminal UI — argument parsing, rendering, the REPL loop, `bin.ts`
packages/shared/  infrastructure both sides use — env loading, logging, ANSI output
eval/           the Langfuse eval harness — datasets, deterministic scorers, the runner
tests/          the suites, mirroring the trees above: `apps/`, `packages/`, `eval/`
```

A UI other than the CLI becomes a sibling of `apps/cli/` and imports `apps/server/index.js`.

## `apps/server/`

`index.ts` is the surface a UI imports — graphs, clients, the record types, and the named
output schemas a caller needs to re-read a structured reply — nothing deeper.

- `agents/` — one directory per graph (`chat/`, `pr-review/`, `issue-review/`), plus
  `shared.ts` for what they have in common. File conventions are in
  [`agents/README.md`](agents/README.md).
- `external/` — dependencies behind interface seams: GitHub in `external/github/`, the model
  in `external/nvidia/`. Each holds a `client.ts` beside the `settings.ts` with its
  constants — the reviewer login, label, and label colour on one side; the base URL, model
  name, and call limits on the other.
- `clients/http.ts` — the provider-agnostic HTTP layer underneath both.

## `apps/cli/`

`bin.ts` is the entry point; `repl.ts` drives the `chat` loop, reading a line at a time and
stopping at `/exit` or Ctrl-D. Everything user-facing — argument parsing, rendering — lives
here and nowhere else.

## `packages/shared/`

Env loading, logging, and ANSI output, used by both apps. See [`LOGS.md`](LOGS.md) for what
the logger writes.

## `eval/`

`npm run eval` scores the review agents against a fixed dataset and sends the run to
[Langfuse](https://langfuse.com). `bin.ts` is the entry point; `run.ts` wires each agent's
dataset, task, and evaluators into one Langfuse experiment. `datasets.ts` holds the cases,
`scorers.ts` the deterministic checks, `tasks.ts` runs the real graph against
`github.ts`'s static repository, and `langfuse.ts` sets up tracing. It imports
`apps/server/index.js` like any other UI. See [`EVAL.md`](EVAL.md).

## `tests/`

One directory per tree above — `apps/`, `packages/`, `eval/` — with `*.integration.test.ts`
marking the suite that speaks HTTP; see [`TESTING.md`](TESTING.md).
