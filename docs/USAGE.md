# Usage

Three commands, one process each: `chat`, `pr_review`, `issue_review`. Every one of them
runs once and exits — there is no daemon and nothing schedules them.

- [Quick start](#quick-start)
- [Commands](#commands) · [`chat`](#chat) · [`pr_review`](#pr_review) · [`issue_review`](#issue_review)
- [Options](#options) — `--dry-run`, `--help`
- [Output and exit codes](#output-and-exit-codes) — sections, the `Usage` totals, color
- [Configuration](#configuration)
- [Known gaps](#known-gaps)

## Quick start

Python 3.14 or newer.

```bash
uv sync                  # install
cp .env.example .env     # then fill in the three variables — see Configuration
uv run angel chat  # talk to the model; no GitHub credentials needed
```

Once the GitHub App variables are set, see what a review run *would* post, without posting
anything:

```bash
uv run angel pr_review --dry-run
```

## Commands

| Command | What it does | Needs |
|---|---|---|
| [`chat`](#chat) | Interactive REPL against the model | NVIDIA key |
| [`pr_review`](#pr_review) | One pass over open PRs labeled `angel`; comments on the ones due for review | NVIDIA key + GitHub App |
| [`issue_review`](#issue_review) | Same, over open issues labeled `angel` | NVIDIA key + GitHub App |

```bash
uv run angel <command> [--dry-run]
```

The command may be given before or after the flag. Anything else exits `1` with
`Unknown command: … Valid commands: chat, pr_review, issue_review`. There is no `--version`
yet.

How each command is wired internally, node by node, is in [`GRAPHS.md`](GRAPHS.md).

### `chat`

```bash
uv run angel chat
```

Reads a line at a time at a `>` prompt and prints the reply. Blank lines are ignored. Leave
with `/exit` or Ctrl-D. The conversation is kept in memory for the life of the process, so
it is gone when you leave — nothing is written to GitHub, and `--dry-run` is rejected here.

### `pr_review`

```bash
uv run angel pr_review [--dry-run]
```

Scans every repository the GitHub App is installed on — the list is discovered at run time,
so granting or revoking the App's access is all it takes to add or drop a repository — and
reviews the open pull requests labeled `angel`.

A labeled PR is reviewed when:

- `kandy-angel[bot]` has **never** commented on it, or
- its **head sha differs** from the one recorded in that last bot comment — so it is
  re-reviewed exactly when the head moves, force-pushes included.

Otherwise it is skipped as already up to date. Each review is posted as one issue comment
on the PR, ending with a `<!-- angel: sha=<head sha> -->` marker. That marker is the
only state the bot keeps: it records which head was reviewed, on the PR itself. Deleting it
from a comment makes the next run review that PR again.

Each PR is read three times, by three specialised prompts — **security**, **quality**, and
**performance** — each told to stay in its lane and given the same title, description, existing
comments, and diff. Three model calls per PR, so three times the tokens and roughly three times
the wall clock of a single pass.

The comment is rendered from validated schemas, not pasted from the model: one summary line per
lens, then a `### Security` / `### Quality` / `### Performance` section, each holding one bold
entry per finding tagged `[blocker]`, `[major]`, `[minor]`, or `[nit]` and pointing at a file and
line where the diff makes that clear. A reply that does not fit the schema — or any one lens
failing — is a failure for that PR: nothing is posted, the run moves on, and the PR is picked up
again next run because no marker was written.

Sampling is pinned at `temperature=0`, so two runs over an unchanged head give the same review far
more often than they used to — though nothing about a hosted model guarantees it.

> **The label is created for you.** Every scanned repository gets a pink `angel` label
> if it lacks one — including repositories you never meant to review. Install the App only
> where you want that.

### `issue_review`

```bash
uv run angel issue_review [--dry-run]
```

The same pass over open issues labeled `angel`. An issue is reviewed when the bot has
never commented on it, or when the issue's `updated_at` is newer than that last comment —
which covers an edited description and new comments alike. The label caveat above applies
here too. The comment follows the same rendered-from-schema shape, with two extra sections:
proposed acceptance criteria and a suggested approach.

## Options

| Option | Works with | Effect |
|---|---|---|
| `--dry-run` | `pr_review`, `issue_review` | Print each review to stdout and make zero GitHub writes |
| `--help` | every command, and on its own | Print usage and exit `0` — also what a bare `uv run angel` does |

### `--dry-run`

The run is identical up to the point of writing: repositories are discovered, labeled items
are selected, diffs are fetched, and the model is called — so it costs the same tokens.
Only the two writes are suppressed: creating the `angel` label, and posting the review
comment. Each review body is printed instead, under its target:

```
Reviews ────────────────────────────────────────────────────────────────

owner/repo#12
The change looks correct, but one branch is untested.

### Findings

**[major] New branch in `parse()` is untested** — `src/parse.py:42`
The early return added here is not covered by any case in `tests/test_parse.py`.
```

The target line is bold; the body is printed unindented and unstyled so it can be copied
straight into a comment as markdown.

Every suppressed write is also logged; see [`LOGS.md`](LOGS.md). Exit codes are unchanged —
a fetch or model failure still reports and exits `1`.

### `--help`

Each command's options, printed either way — nothing runs, no credentials are read:

```bash
uv run angel pr_review --help
uv run angel help pr_review
```

```
usage: angel pr_review [-h] [--dry-run]

Review open pull requests labeled angel.

options:
  -h, --help  show this help message and exit
  --dry-run   Print each review to stdout and make zero GitHub writes
```

`uv run angel --help`, a bare `help`, or `uv run angel` with no arguments at all
lists the three commands instead — the same output and the same exit `0` from each. Naming
something that is not a command still exits `1` with the usual `Unknown command: …`, whether
it is `uv run angel bogus` or `uv run angel help bogus`.

## Output and exit codes

A run prints three sections to stdout — what it is doing, what it produced, and what it
cost:

```
Run ────────────────────────────────────────────────────────────────────

  command   pr_review
  dry run   no
  log       log/angel-20260816T101010Z.jsonl

Reviews ────────────────────────────────────────────────────────────────

  Commented on owner/repo#12
  Commented on owner/other#3

Usage ──────────────────────────────────────────────────────────────────

  calls                6
  input_tokens    12,345
  output_tokens    2,048
  total_tokens    14,393
  duration_ms     8213.4
```

When nothing was due, the `Reviews` section holds the one line it always did —
`No pull requests to review` or `No issues to review` — and `Usage` still prints.

### The `Usage` section

The per-run total of every call into the model, summed from the same numbers the
`model call completed` records carry in the log — see [`LOGS.md`](LOGS.md) for the per-call
detail. The field names match those records exactly:

| Field | Meaning |
|---|---|
| `calls` | how many times the model was called, `complete` and `complete_structured` together |
| `input_tokens` / `output_tokens` / `total_tokens` | summed across those calls; a provider that returns no usage metadata contributes `0` while still counting toward `calls` |
| `duration_ms` | wall time inside the provider calls, milliseconds — not the run's total wall time |

`chat` prints the same section when the session ends. The section is printed **before** the
process exits non-zero, so a failed run still reports what it spent.

### Color

Colored when stdout is a terminal, plain otherwise — so piping or redirecting is unaffected.
`ANGEL_COLOR` overrides the terminal check in either direction, and a non-empty
`NO_COLOR` always wins. Only the section headings and the status lines are styled; review
bodies are never colored.

### Failures

Each repository and each item is isolated, so one failure never discards the rest of the
work — a model error on the fifth pull request still leaves the other nine reviewed and
posted. What failed prints to stderr under its own heading, one line each, followed by a
count:

```
Failures ───────────────────────────────────────────────────────────────

Failed review_pull_requests for owner/repo#12: HTTPStatusError: 500 Server Error
Failed post_review_comments for owner/other: TimeoutError:
2 of 5 items failed
```

Repository-level failures — one repository of thirty unreachable during the scan — carry no
item number and print as `owner/repo`. Because failures go to stderr and the three sections
above go to stdout, `2> /dev/null` keeps the report and drops the errors.

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
| `ANGEL_NVIDIA_API_KEY` | all three commands | NVIDIA API key from https://build.nvidia.com — used for every model call. |
| `ANGEL_GITHUB_APP_ID` | `pr_review`, `issue_review` | ID of the GitHub App to authenticate as. |
| `ANGEL_GITHUB_PRIVATE_KEY_PATH` | `pr_review`, `issue_review` | Path to that App's private key (`.pem`). |
| `ANGEL_NVIDIA_MAX_COMPLETION_TOKENS` | optional, all three commands | Output tokens allowed per model call, default `32768`. Counts the model's reasoning as well as its answer, so a value sized to the review text alone truncates the reply mid-object and the item fails. A non-integer or non-positive value exits `1` rather than falling back to the default. |
| `ANGEL_COLOR` | optional, all three commands | `auto` (default) colors the console only when the stream is a terminal; `always` keeps color when piping or redirecting; `never` disables it. An unrecognised value is treated as `auto`. A non-empty `NO_COLOR` disables color whatever this is set to. |

A missing *required* variable exits `1` with `<NAME> environment variable is not set.` before
any work starts. `.env` is loaded automatically and searched from the current directory *upward*, so
run the commands from the project root; an already-exported shell variable takes precedence
over the file.

### The GitHub App

[kandy-angel](https://github.com/apps/kandy-angel) is the App behind the
reviews. The repositories it reviews are exactly the ones it is installed on — there is no
list to maintain in the code. It needs three permissions and nothing more, so it cannot
approve, merge, or push:

| Permission | Used for |
|---|---|
| **Pull requests: read** | listing PRs and fetching diffs |
| **Issues: read and write** | reading issues and comments, creating the `angel` label, posting the review comment |
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
