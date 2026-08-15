# Usage

## Configuration

Copy `.env.example` to `.env` and fill in the variables below.

| Variable | Command | Required | Description |
|---|---|---|---|
| `NISHIKIHEBI_NVIDIA_API_KEY` | `chat`, `pr_review`, `issue_review` | Yes | NVIDIA API key from https://build.nvidia.com — used for all model calls. |
| `NISHIKIHEBI_GITHUB_APP_ID` | `pr_review`, `issue_review` | Yes for `pr_review`, `issue_review` | ID of the GitHub App used to authenticate — [kandy-nishikihebi](https://github.com/apps/kandy-nishikihebi) is the App behind the PR and issue reviews. It needs **Pull requests: read** (list PRs, fetch diffs), **Issues: read and write** (read issues and comments, create the `nishikihebi` label, post the review comment), **Contents: read** (head commit dates), and **Metadata: read**. Nothing more — it cannot approve, merge, or push. The repositories to review are whichever ones the App is installed on — there is no list to maintain in the code. |
| `NISHIKIHEBI_GITHUB_PRIVATE_KEY_PATH` | `pr_review`, `issue_review` | Yes for `pr_review`, `issue_review` | Path to the GitHub App's private key (`.pem`). |

The app loads `.env` automatically; an already-exported shell variable still takes precedence.

## Running

Python 3.14 or newer is required.

```bash
uv sync
uv run nishikihebi chat           # interactive REPL; leave with /exit or Ctrl-D
uv run nishikihebi pr_review
uv run nishikihebi issue_review
uv run ci                         # ruff check, then basedpyright, then pytest
```

Each command runs once and exits — `pr_review` and `issue_review` scan, review, post, and
stop. Nothing schedules them yet. See [`TODO.md`](TODO.md) §8.1 for the deployment options
and §9 for the flags that are still missing, `--dry-run` most of all: there is currently no
way to see what a review run *would* post without posting it.

What each run writes to the console and to disk is documented in [`LOGS.md`](LOGS.md).
