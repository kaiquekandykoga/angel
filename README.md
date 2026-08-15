# Nishikihebi

A Python CLI built on [LangGraph](https://langchain-ai.github.io/langgraph/) state graphs,
backed by an NVIDIA-hosted model. It offers three commands: an interactive `chat` REPL,
plus `pr_review` and `issue_review`, which act as the
[kandy-nishikihebi](https://github.com/apps/kandy-nishikihebi) GitHub App and automatically
comment on pull requests and issues labeled `nishikihebi` across the repositories the App
is installed on.

## Docs

- [`docs/USAGE.md`](docs/USAGE.md) — the environment variables each command needs, how the
  GitHub App is configured, and the commands themselves. **Start here.**
- [`docs/GRAPHS.md`](docs/GRAPHS.md) — how each of the three graphs is wired, node by node,
  with a diagram per command and how the code is laid out under `src/nishikihebi/agents/`.
- [`docs/LOGS.md`](docs/LOGS.md) — what each run writes to the console and to
  `log/nishikihebi-<timestamp>.jsonl`, the shape of a log record, and how to read a run
  back with `jq`.
- [`docs/TODO.md`](docs/TODO.md) — what stands between this and running unattended:
  pagination, retries, prompt-injection hardening, a deployment story, ending with a
  prioritized roadmap. A living document — each item is marked open or done, and there is
  a changelog at the bottom.
