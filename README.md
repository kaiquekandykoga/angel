# Angel

A TypeScript CLI built on [LangGraph](https://langchain-ai.github.io/langgraphjs/) state graphs,
backed by an NVIDIA-hosted model. It offers three commands: an interactive `chat` REPL,
plus `pr_review` and `issue_review`, which act as the
[kandy-angel](https://github.com/apps/kandy-angel) GitHub App and automatically
comment on pull requests and issues labeled `angel` across the repositories the App
is installed on.

```bash
npm install
cp .env.example .env     # then fill in the variables — see docs/USAGE.md
npm run angel chat       # talk to the model; no GitHub credentials needed
```

## Docs

- [`docs/USAGE.md`](docs/USAGE.md) — every command and option, what each one prints and
  exits with, and the environment variables and GitHub App they need. **Start here.**
- [`docs/GRAPHS.md`](docs/GRAPHS.md) — how each of the three graphs is wired, node by node,
  with a diagram per command and how the code is laid out under `src/agents/`.
- [`docs/LOGS.md`](docs/LOGS.md) — what each run writes to the console and to
  `log/angel-<timestamp>.jsonl`, the shape of a log record, and how to read a run
  back with `jq`.
- [`docs/TESTING.md`](docs/TESTING.md) — how the unit and integration suites are split, why
  both exist, and how to add a recorded GitHub fixture.
- [`docs/TODO.md`](docs/TODO.md) — the living backlog of what stands between this and
  running unattended: retries, prompt-injection hardening, a deployment story.
  Open items only, grouped P0/P1/P2, with the conventions for adding new items at the top.

## Limitations

This is a working tool, not a hardened service. Before you point it at anything you care about:

- **Nothing schedules a run.** Both review commands are one-shot; there is no daemon and no
  webhook listener.
- **No rate-limit or backoff handling.** A run that hits GitHub's secondary limit fails the
  affected items instead of waiting.
- **Untrusted input reaches the model undelimited.** PR bodies, issue bodies, comments, and
  diffs are interpolated into the prompt, and the reply is posted under the App's identity.
- **The full diff is sent with no cap.** A lockfile touch can blow the context window.
- **Installation tokens are cached for the life of the run** and never refreshed, so a run
  longer than an hour will start failing with 401s.
- **The reviewer login is hardcoded** to `kandy-angel[bot]` in `src/settings.ts`; running this
  as your own App means editing that constant.

Each is tracked in [`docs/TODO.md`](docs/TODO.md).

## License

BSD-3-Clause. See [`LICENSE`](LICENSE).
