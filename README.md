# Nishikihebi

A Python CLI built on [LangGraph](https://langchain-ai.github.io/langgraph/) state graphs,
backed by an NVIDIA-hosted model. It offers three commands: an interactive `chat` REPL,
plus `pr_review` and `issue_review`, which act as the
[kandy-nishikihebi](https://github.com/apps/kandy-nishikihebi) GitHub App and automatically
comment on pull requests and issues labeled `nishikihebi` across the repositories the App
is installed on.

## Docs

- [`docs/USAGE.md`](docs/USAGE.md) — every command and option, what each one prints and
  exits with, and the environment variables and GitHub App they need. **Start here.**
- [`docs/GRAPHS.md`](docs/GRAPHS.md) — how each of the three graphs is wired, node by node,
  with a diagram per command and how the code is laid out under `src/nishikihebi/agents/`.
- [`docs/LOGS.md`](docs/LOGS.md) — what each run writes to the console and to
  `log/nishikihebi-<timestamp>.jsonl`, the shape of a log record, and how to read a run
  back with `jq`.
- [`docs/TESTING.md`](docs/TESTING.md) — how the unit and integration suites are split, why
  both exist, and how to add a recorded GitHub fixture.
- [`docs/TODO.md`](docs/TODO.md) — the living backlog of what stands between this and
  running unattended: retries, prompt-injection hardening, a deployment story.
  Open items only, grouped P0/P1/P2, with the conventions for adding new items at the top.
