# Angel

Angel is an automated code reviewer: a TypeScript CLI, built on
[LangGraph](https://langchain-ai.github.io/langgraphjs/) state graphs and backed by an
NVIDIA-hosted model, that reads pull requests and issues on GitHub and leaves a review
comment on them.

It runs as the [kandy-angel](https://github.com/apps/kandy-angel) GitHub App. Each run
discovers every repository the App is installed on, picks up the open items labeled
`angel`, and comments on the ones that have changed since it last looked — a PR whose head
sha moved, an issue edited or commented on. There is no daemon and nothing schedules it:
one command, one pass, then exit.

Three commands:

| Command | What it does |
|---|---|
| `chat` | An interactive REPL against the model — no GitHub credentials needed |
| `pr_review` | Reviews open pull requests labeled `angel` through three prompts — security, quality, performance — and posts one comment merging them |
| `issue_review` | Reviews open issues labeled `angel` in one pass, adding proposed acceptance criteria and a suggested approach |

Reviews are rendered from validated schemas rather than pasted from the model, so every
finding carries a severity and a file:line the diff supports. PR titles, descriptions,
comments, and diffs are attacker-controlled, so they reach the model fenced under a policy
that forbids following instructions found inside them, and every posted body is sanitised
and capped on the way out. `--dry-run` does everything except write to GitHub.

## Docs

| Doc | Covers |
|---|---|
| [`docs/USAGE.md`](docs/USAGE.md) | **Start here** — every command and option, what each prints and exits with, the environment variables and GitHub App they need |
| [`docs/INSTALL.md`](docs/INSTALL.md) | Requirements, and installing from source or globally |
| [`docs/LAYOUT.md`](docs/LAYOUT.md) | The directory tree and what lives where, from `apps/server/` down to the client seams |
| [`docs/agents/`](docs/agents/README.md) | How each graph is wired, node by node, with a page and diagram per command: [`chat`](docs/agents/CHAT.md), [`pr_review`](docs/agents/PR-REVIEW.md), [`issue_review`](docs/agents/ISSUE-REVIEW.md) |
| [`docs/LOGS.md`](docs/LOGS.md) | What a run writes to the console and to `log/angel-<timestamp>.jsonl`, the record shape, and how to read a run back with `jq` |
| [`docs/TESTING.md`](docs/TESTING.md) | How the unit and integration suites split, why both exist, and how to add a recorded GitHub fixture |
| [`docs/EVAL.md`](docs/EVAL.md) | `npm run eval` — scoring the review agents against a fixed dataset with deterministic checks, and sending the run to Langfuse |
| [`docs/TODO.md`](docs/TODO.md) | The living backlog between this and running unattended: retries, prompt-injection hardening, a deployment story. Open items only, grouped P0/P1/P2 |

## License

BSD-3-Clause. See [`LICENSE`](LICENSE).
