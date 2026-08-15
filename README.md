# Nishikihebi

A Python CLI built on [LangGraph](https://langchain-ai.github.io/langgraph/) state graphs,
backed by an NVIDIA-hosted model. It offers three commands: an interactive `chat` REPL,
plus `pr_review` and `issue_review`, which act as the
[kandy-nishikihebi](https://github.com/apps/kandy-nishikihebi) GitHub App and automatically
comment on pull requests and issues labeled `nishikihebi` across the repositories the App
is installed on.

## Usage

Copy `.env.example` to `.env` and fill in the variables below.

| Variable | Command | Required | Description |
|---|---|---|---|
| `NISHIKIHEBI_NVIDIA_API_KEY` | `chat`, `pr_review`, `issue_review` | Yes | NVIDIA API key from https://build.nvidia.com — used for all model calls. |
| `NISHIKIHEBI_GITHUB_APP_ID` | `pr_review`, `issue_review` | Yes for `pr_review`, `issue_review` | ID of the GitHub App used to authenticate — [kandy-nishikihebi](https://github.com/apps/kandy-nishikihebi) is the App behind the PR and issue reviews. It needs **Pull requests: read** (list PRs, fetch diffs), **Issues: read and write** (read issues and comments, create the `nishikihebi` label, post the review comment), **Contents: read** (head commit dates), and **Metadata: read**. Nothing more — it cannot approve, merge, or push. The repositories to review are whichever ones the App is installed on — there is no list to maintain in the code. |
| `NISHIKIHEBI_GITHUB_PRIVATE_KEY_PATH` | `pr_review`, `issue_review` | Yes for `pr_review`, `issue_review` | Path to the GitHub App's private key (`.pem`). |

The app loads `.env` automatically; an already-exported shell variable still takes precedence.

Python 3.14 or newer is required.

```bash
uv sync
uv run nishikihebi chat           # interactive REPL; leave with /exit or Ctrl-D
uv run nishikihebi pr_review
uv run nishikihebi issue_review
uv run ci                         # ruff check, then basedpyright, then pytest
```

## Graphs

Each command is a [LangGraph](https://langchain-ai.github.io/langgraph/) state graph
assembled in `src/nishikihebi/graphs/` — `graphs/chat/chat.py` for `chat`, and
`graphs/github/` for the two review commands. The graphs only wire nodes together — the
nodes in `src/nishikihebi/nodes/` (`nodes/chat/`, `nodes/github/`) are factories that take
their dependencies (LLM client, GitHub client) and return the node function, so a graph
can be built against fakes in tests. Those dependencies sit behind `Protocol` seams in
`src/nishikihebi/clients/`, and the state threaded between nodes lives in
`src/nishikihebi/states/`.

### `chat`

An interactive assistant REPL over a one-node graph. `chat/cli.py` reads a line at a time
and stops at `/exit` or end of input (Ctrl-D); `chat/session.py` holds the `thread_id`
generated when the session starts and invokes the graph once per line. The conversation
grows because `ChatState.messages` uses the `add_messages` reducer and the compiled graph
carries a checkpointer (`MemorySaver` by default), so each invocation appends to that same
thread — and the history lives only in memory, so it ends with the process.

```
  START
    |
    v
  +----------+
  | call_llm |  <--- NVIDIA model: system prompt + conversation so far
  +----------+
    |  reply appended to state["messages"]
    v
   END
```

`call_llm` prepends the system prompt to the accumulated messages, calls the model, and
returns the reply for the reducer to append.

### `pr_review`

Reviews open pull requests across every repository the App installation can reach — the
set is discovered at run time from GitHub, so granting or revoking the App's access to a
repository is all it takes to add or drop it. Only PRs labeled `nishikihebi` are
considered; the label is created on each repository if it doesn't already exist. A
labeled pull request is picked up when `kandy-nishikihebi[bot]` has never commented on
it, or when its head commit is newer than that last comment — so a PR is re-reviewed only
after new commits land.

```
  START
    |
    v
  +---------------------+
  | fetch_pull_requests |  <--- GitHub: installation repositories,
  +---------------------+       ensures the `nishikihebi` label exists,
    |                           then their open PRs labeled `nishikihebi` + comments
    |  PullRequestContext (pull request + comments), only the ones due for review
    v
  +----------------------+
  | review_pull_requests |  <--- GitHub: the PR diff
  +----------------------+  <--- NVIDIA model: one review comment
    |  Review (target + body)
    v
  +----------------------+
  | post_review_comments |  ---> GitHub: comment posted on the PR
  +----------------------+
    |
    v
   END
```

| Node | Does |
|---|---|
| `fetch_pull_requests` | Ensures each repository has the `nishikihebi` label, lists PRs carrying it and their comments, keeps the ones due for review, and emits `PullRequestContext` (the PR plus its comments) |
| `review_pull_requests` | Fetches the diff and asks the model for one review comment, given the title, description, existing comments, and diff |
| `post_review_comments` | Posts each review as an issue comment on its PR |

### `issue_review`

Same shape as `pr_review`, over the open issues of the same discovered repositories. Only
issues labeled `nishikihebi` are considered; the label is created on each repository if
it doesn't already exist. A labeled issue is picked up when `kandy-nishikihebi[bot]` has
never commented on it, or when the issue's `updated_at` is newer than that last comment —
which covers both an edited description and new comments.

```
  START
    |
    v
  +--------------+
  | fetch_issues |  <--- GitHub: installation repositories,
  +--------------+       ensures the `nishikihebi` label exists,
    |                    then their open issues labeled `nishikihebi` + comments
    |  IssueContext (issue + comments), only the ones due for review
    v
  +---------------+
  | review_issues |  <--- NVIDIA model: one review comment
  +---------------+
    |  Review (target + body)
    v
  +----------------------+
  | post_review_comments |  ---> GitHub: comment posted on the issue
  +----------------------+
    |
    v
   END
```

| Node | Does |
|---|---|
| `fetch_issues` | Ensures each repository has the `nishikihebi` label, lists issues carrying it and their comments, keeps the ones due for review, and emits `IssueContext` (the issue plus its comments) |
| `review_issues` | Asks the model for one review comment, given the title, description, and existing comments |
| `post_review_comments` | Shared with `pr_review` — posts each review as an issue comment |

## Logs

High-level progress is printed to the console. Every run also writes a detailed log to
`log/nishikihebi-<timestamp>.jsonl` — one JSON object per line, carrying the structured
fields each node attaches (repository, PR/issue number, counts, and so on). `log/` is
gitignored.

## Docs

[`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md) reviews what stands between
this and running unattended — pagination, retries, prompt-injection hardening, a
deployment story — and ends with a prioritized roadmap. The gaps it lists are known and
still open; it is being worked through step by step.
