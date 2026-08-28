# Angel

A TypeScript CLI on [LangGraph](https://langchain-ai.github.io/langgraphjs/) state graphs,
backed by an NVIDIA-hosted model. Three commands: an interactive `chat` REPL, plus
`pr_review` and `issue_review`, which act as the
[kandy-angel](https://github.com/apps/kandy-angel) GitHub App and comment on pull requests
and issues labeled `angel` across the repositories the App is installed on.

## Docs

- [`docs/INSTALL.md`](docs/INSTALL.md) — requirements and how to install, from source or
  globally.
- [`docs/USAGE.md`](docs/USAGE.md) — every command and option, what each prints and exits
  with, the environment variables and GitHub App they need. **Start here.**
- [`docs/LAYOUT.md`](docs/LAYOUT.md) — the directory tree and what lives where, from
  `apps/server/` down to the client seams.
- [`docs/agents/`](docs/agents/README.md) — how each of the three graphs is wired, node by
  node, with a page and diagram per command: [`chat`](docs/agents/CHAT.md),
  [`pr_review`](docs/agents/PR-REVIEW.md), [`issue_review`](docs/agents/ISSUE-REVIEW.md).
- [`docs/LOGS.md`](docs/LOGS.md) — what each run writes to the console and to
  `log/angel-<timestamp>.jsonl`, the shape of a log record, and how to read a run back with
  `jq`.
- [`docs/TESTING.md`](docs/TESTING.md) — how the unit and integration suites split, why both
  exist, and how to add a recorded GitHub fixture.
- [`docs/EVAL.md`](docs/EVAL.md) — `npm run eval`: scoring the review agents against a fixed
  dataset with deterministic checks, and sending the run to Langfuse.
- [`docs/TODO.md`](docs/TODO.md) — the living backlog between this and running unattended:
  retries, prompt-injection hardening, a deployment story. Open items only, grouped
  P0/P1/P2, conventions for new items at the top.

## License

BSD-3-Clause. See [`LICENSE`](LICENSE).
