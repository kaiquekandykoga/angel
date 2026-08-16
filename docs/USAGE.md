# Usage

Three commands, one process each: `chat`, `pr_review`, `issue_review`. Every one of them
runs once and exits — there is no daemon and nothing schedules them.

- [Quick start](#quick-start)
- [Commands](#commands) · [`chat`](#chat) · [`pr_review`](#pr_review) · [`issue_review`](#issue_review)
- [Options](#options) — `--dry-run`, `--help`
- [Output and exit codes](#output-and-exit-codes)
- [Configuration](#configuration)
- [Known gaps](#known-gaps)

## Quick start

Python 3.14 or newer.

```bash
uv sync                  # install
cp .env.example .env     # then fill in the three variables — see Configuration
uv run nishikihebi chat  # talk to the model; no GitHub credentials needed
```

Once the GitHub App variables are set, see what a review run *would* post, without posting
anything:

```bash
uv run nishikihebi pr_review --dry-run
```

## Commands

| Command | What it does | Needs |
|---|---|---|
| [`chat`](#chat) | Interactive REPL against the model | NVIDIA key |
| [`pr_review`](#pr_review) | One pass over open PRs labeled `nishikihebi`; comments on the ones due for review | NVIDIA key + GitHub App |
| [`issue_review`](#issue_review) | Same, over open issues labeled `nishikihebi` | NVIDIA key + GitHub App |

```bash
uv run nishikihebi <command> [--dry-run]
```

The command may be given before or after the flag. Anything else exits `1` with
`Unknown command: … Valid commands: chat, pr_review, issue_review`. There is no `--version`
yet.

How each command is wired internally, node by node, is in [`GRAPHS.md`](GRAPHS.md).

### `chat`

```bash
uv run nishikihebi chat
```

Reads a line at a time at a `>` prompt and prints the reply. Blank lines are ignored. Leave
with `/exit` or Ctrl-D. The conversation is kept in memory for the life of the process, so
it is gone when you leave — nothing is written to GitHub, and `--dry-run` is rejected here.

### `pr_review`

```bash
uv run nishikihebi pr_review [--dry-run]
```

Scans every repository the GitHub App is installed on — the list is discovered at run time,
so granting or revoking the App's access is all it takes to add or drop a repository — and
reviews the open pull requests labeled `nishikihebi`.

A labeled PR is reviewed when:

- `kandy-nishikihebi[bot]` has **never** commented on it, or
- its **head sha differs** from the one recorded in that last bot comment — so it is
  re-reviewed exactly when the head moves, force-pushes included.

Otherwise it is skipped as already up to date. Each review is posted as one issue comment
on the PR, ending with a `<!-- nishikihebi: sha=<head sha> -->` marker. That marker is the
only state the bot keeps: it records which head was reviewed, on the PR itself. Deleting it
from a comment makes the next run review that PR again.

The comment is rendered from a validated schema, not pasted from the model: a summary
paragraph, then one bold entry per finding tagged `[blocker]`, `[major]`, `[minor]`, or
`[nit]` and pointing at a file and line where the diff makes that clear. A reply that does
not fit the schema is a failure for that PR — nothing is posted — and the run moves on.

> **The label is created for you.** Every scanned repository gets a pink `nishikihebi` label
> if it lacks one — including repositories you never meant to review. Install the App only
> where you want that.

### `issue_review`

```bash
uv run nishikihebi issue_review [--dry-run]
```

The same pass over open issues labeled `nishikihebi`. An issue is reviewed when the bot has
never commented on it, or when the issue's `updated_at` is newer than that last comment —
which covers an edited description and new comments alike. The label caveat above applies
here too. The comment follows the same rendered-from-schema shape, with two extra sections:
proposed acceptance criteria and a suggested approach.

## Options

| Option | Works with | Effect |
|---|---|---|
| `--dry-run` | `pr_review`, `issue_review` | Print each review to stdout and make zero GitHub writes |
| `--help` | every command, and on its own | Print usage and exit `0` |

### `--dry-run`

The run is identical up to the point of writing: repositories are discovered, labeled items
are selected, diffs are fetched, and the model is called — so it costs the same tokens.
Only the two writes are suppressed: creating the `nishikihebi` label, and posting the review
comment. Each review body is printed instead:

```
--- owner/repo#12 ---
The change looks correct, but one branch is untested.

### Findings

**[major] New branch in `parse()` is untested** — `src/parse.py:42`
The early return added here is not covered by any case in `tests/test_parse.py`.
```

Every suppressed write is also logged; see [`LOGS.md`](LOGS.md). Exit codes are unchanged —
a fetch or model failure still reports and exits `1`.

### `--help`

Each command's options, printed either way — nothing runs, no credentials are read:

```bash
uv run nishikihebi pr_review --help
uv run nishikihebi help pr_review
```

```
usage: nishikihebi pr_review [-h] [--dry-run]

Review open pull requests labeled nishikihebi.

options:
  -h, --help  show this help message and exit
  --dry-run   Print each review to stdout and make zero GitHub writes
```

`uv run nishikihebi --help`, or a bare `help`, lists the three commands instead. `help` with
an unknown name exits `1` with the usual `Unknown command: …`.

## Output and exit codes

A review run prints one line per posted review, or a single line when nothing was due:

```
Commented on owner/repo#12
Commented on owner/other#3
```
```
No pull requests to review
```

Each repository and each item is isolated, so one failure never discards the rest of the
work — a model error on the fifth pull request still leaves the other nine reviewed and
posted. What failed prints to stderr, one line each, followed by a count:

```
Failed review_pull_requests for owner/repo#12: HTTPStatusError: 500 Server Error
Failed post_review_comments for owner/other: TimeoutError:
2 of 5 items failed
```

Repository-level failures — one repository of thirty unreachable during the scan — carry no
item number and print as `owner/repo`.

| Exit code | Meaning |
|---|---|
| `0` | every item due for review was reviewed and posted (including the case where nothing was due) |
| `1` | at least one repository or item failed, or the command was invalid, or credentials were missing |

The non-zero exit is what makes a scheduler notice. The same failures appear as `WARNING`
records in the JSON log with structured `stage` / `error_type` fields; what every run writes
to the console and to `log/` is documented in [`LOGS.md`](LOGS.md).

## Configuration

Copy `.env.example` to `.env` and fill in these variables.

| Variable | Needed by | Description |
|---|---|---|
| `NISHIKIHEBI_NVIDIA_API_KEY` | all three commands | NVIDIA API key from https://build.nvidia.com — used for every model call. |
| `NISHIKIHEBI_GITHUB_APP_ID` | `pr_review`, `issue_review` | ID of the GitHub App to authenticate as. |
| `NISHIKIHEBI_GITHUB_PRIVATE_KEY_PATH` | `pr_review`, `issue_review` | Path to that App's private key (`.pem`). |

A missing variable exits `1` with `<NAME> environment variable is not set.` before any work
starts. `.env` is loaded automatically and searched from the current directory *upward*, so
run the commands from the project root; an already-exported shell variable takes precedence
over the file.

### The GitHub App

[kandy-nishikihebi](https://github.com/apps/kandy-nishikihebi) is the App behind the
reviews. The repositories it reviews are exactly the ones it is installed on — there is no
list to maintain in the code. It needs three permissions and nothing more, so it cannot
approve, merge, or push:

| Permission | Used for |
|---|---|
| **Pull requests: read** | listing PRs and fetching diffs |
| **Issues: read and write** | reading issues and comments, creating the `nishikihebi` label, posting the review comment |
| **Metadata: read** | required by the others |

## Testing

`uv run ci` runs the whole gate — `ruff check`, then `basedpyright`, then `pytest`:

```bash
uv run ci
uv run pytest -m "not integration"   # fakes only, fastest
uv run pytest -m integration         # client code over recorded GitHub payloads
```

Neither suite touches the network. How the two trees differ, and how to add a fixture, is
in [`TESTING.md`](TESTING.md).

## Known gaps

- **Nothing schedules a run.** Both review commands are one-shot; see [`TODO.md`](TODO.md),
  "Pick a deployment story".
- **The CLI has no scoping flags** — no `--version`, and no `--repo owner/name`, `--limit N`,
  `--log-level`, or `--log-file`. See "Finish the CLI flags".
- **Some failures still print a traceback** rather than a message — a bad private-key path,
  an expired key, or Ctrl-C out of `chat`. See "Fail with a message, not a traceback".
- **No rate-limit or backoff handling.** A run that hits GitHub's secondary limit fails the
  affected items instead of waiting.
