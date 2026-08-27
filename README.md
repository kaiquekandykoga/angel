# Angel

A TypeScript CLI on [LangGraph](https://langchain-ai.github.io/langgraphjs/) state graphs,
backed by an NVIDIA-hosted model. Three commands: an interactive `chat` REPL, plus
`pr_review` and `issue_review`, which act as the
[kandy-angel](https://github.com/apps/kandy-angel) GitHub App and comment on pull requests
and issues labeled `angel` across the repositories the App is installed on.

```bash
npm install
cp .env.example .env     # then fill in the variables — see docs/USAGE.md
npm run angel chat       # talk to the model; no GitHub credentials needed
```

## Docs

- [`docs/USAGE.md`](docs/USAGE.md) — every command and option, what each prints and exits
  with, the environment variables and GitHub App they need. **Start here.**
- [`docs/GRAPHS.md`](docs/GRAPHS.md) — how each of the three graphs is wired, node by node,
  with a diagram per command and the code layout under `src/agents/`.
- [`docs/LOGS.md`](docs/LOGS.md) — what each run writes to the console and to
  `log/angel-<timestamp>.jsonl`, the shape of a log record, and how to read a run back with
  `jq`.
- [`docs/TESTING.md`](docs/TESTING.md) — how the unit and integration suites split, why both
  exist, and how to add a recorded GitHub fixture.
- [`docs/TODO.md`](docs/TODO.md) — the living backlog between this and running unattended:
  retries, prompt-injection hardening, a deployment story. Open items only, grouped
  P0/P1/P2, conventions for new items at the top.

## Limitations

A working tool, not a hardened service. Before pointing it at anything you care about:

- **Nothing schedules a run.** Both review commands are one-shot; no daemon, no webhook
  listener.
- **No rate-limit or backoff handling.** A run hitting GitHub's secondary limit fails the
  affected items instead of waiting.
- **Untrusted input reaches the model undelimited.** PR/issue bodies, comments, and diffs
  are interpolated into the prompt, and the reply posts under the App's identity.
- **The full diff is sent with no cap.** A lockfile touch can blow the context window.
- **Installation tokens are cached for the run's life** and never refreshed, so a run
  longer than an hour starts failing with 401s.
- **The reviewer login is hardcoded** to `kandy-angel[bot]` in `src/settings.ts`; running
  this as your own App means editing that constant.

Each is tracked in [`docs/TODO.md`](docs/TODO.md).

## License

BSD-3-Clause. See [`LICENSE`](LICENSE).
