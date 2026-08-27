# Usage

Three commands, one process each: `chat`, `pr_review`, `issue_review`. Each runs once and
exits — no daemon, nothing schedules them.

- [Quick start](#quick-start)
- [Commands](#commands) · [`chat`](#chat) · [`pr_review`](#pr_review) · [`issue_review`](#issue_review)
- [Options](#options) — `--dry-run`, `--help`
- [Output and exit codes](#output-and-exit-codes) — sections, `Usage` totals, color
- [Configuration](#configuration)
- [Testing](#testing)
- [Known gaps](#known-gaps)

## Quick start

Node 22 or newer.

```bash
npm install              # install
cp .env.example .env     # then fill in the three variables — see Configuration
npm run angel chat       # talk to the model; no GitHub credentials needed
```

`npm run angel` runs the TypeScript sources through [`tsx`](https://tsx.is). Compiled build,
same behavior:

```bash
npm run build
node dist/apps/cli/bin.js chat
```

Preview what a review run would post, without posting anything (needs the GitHub App
variables):

```bash
npm run angel pr_review -- --dry-run
```

> `npm run` swallows flags unless separated with `--`. `node dist/apps/cli/bin.js pr_review
> --dry-run` or an installed `angel pr_review --dry-run` needs no separator.

## Commands

| Command | What it does | Needs |
|---|---|---|
| [`chat`](#chat) | Interactive REPL against the model | NVIDIA key |
| [`pr_review`](#pr_review) | One pass over open PRs labeled `angel`; comments on the ones due for review | NVIDIA key + GitHub App |
| [`issue_review`](#issue_review) | Same, over open issues labeled `angel` | NVIDIA key + GitHub App |

```bash
angel <command> [--dry-run]
```

Command may come before or after the flag. Anything else exits `1` with `Unknown command: …
Valid commands: chat, pr_review, issue_review`. No `--version` yet.

Node-by-node wiring of each command is in [`GRAPHS.md`](GRAPHS.md).

### `chat`

```bash
angel chat
```

Reads a line at a `>` prompt, prints the reply; blank lines ignored. Exit with `/exit` or
Ctrl-D. Conversation lives in memory for the process's life only — nothing writes to
GitHub, and `--dry-run` is rejected here.

### `pr_review`

```bash
angel pr_review [--dry-run]
```

Scans every repository the GitHub App is installed on (discovered at run time — granting or
revoking access adds or drops a repo) and reviews open pull requests labeled `angel`.

A labeled PR is reviewed when `kandy-angel[bot]` has **never** commented on it, or its
**head sha differs** from the one recorded in that last bot comment — re-reviewed exactly
when the head moves, force-pushes included. Otherwise it's skipped as up to date.

Each review posts as one issue comment ending with a `<!-- angel: sha=<head sha> -->`
marker — the only state the bot keeps, recording which head was reviewed, on the PR itself.
Deleting it makes the next run review that PR again.

Each PR is read three times, by three specialised prompts — **security**, **quality**,
**performance** — each told to stay in its lane and given the same title, description,
comments, and diff: three times the tokens and roughly three times the wall clock of a
single pass.

The comment is rendered from validated schemas, not pasted from the model: one summary line
per lens, then `### Security` / `### Quality` / `### Performance` sections, each holding one
bold entry per finding tagged `[blocker]` / `[major]` / `[minor]` / `[nit]` and a file:line
the diff supports. Any lens failing, or a reply that doesn't fit the schema, fails the whole
PR: nothing posts, and it's retried next run since no marker was written.

`temperature=0`, so repeat runs over an unchanged head usually match — though a hosted model
guarantees nothing.

> **The label is created for you.** Every scanned repository gets a pink `angel` label if it
> lacks one, including repositories you never meant to review. Install the App only where
> you want that.

### `issue_review`

```bash
angel issue_review [--dry-run]
```

Same pass over open issues labeled `angel`. Reviewed when the bot has never commented, or
the issue's `updatedAt` is newer than that last comment (covers an edited description and
new comments alike). Label caveat above applies here too. Same rendered-from-schema shape,
plus two extra sections: proposed acceptance criteria and a suggested approach.

## Options

| Option | Works with | Effect |
|---|---|---|
| `--dry-run` | `pr_review`, `issue_review` | Print each review to stdout and make zero GitHub writes |
| `--help` | every command, and on its own | Print usage and exit `0` — also what a bare `angel` does |

### `--dry-run`

Identical up to the write: repositories discovered, items selected, diffs fetched, model
called — same token cost. Only two writes are suppressed: creating the `angel` label,
posting the comment. Each review body prints instead, under its target:

```
Reviews ────────────────────────────────────────────────────────────────

owner/repo#12
The change looks correct, but one branch is untested.

### Findings

**[major] New branch in `parse()` is untested** — `src/parse.ts:42`
The early return added here is not covered by any case in `tests/unit/parse.test.ts`.
```

Target line is bold; body prints unindented and unstyled, ready to paste as markdown.

Every suppressed write is also logged; see [`LOGS.md`](LOGS.md). Exit codes unchanged — a
fetch or model failure still exits `1`.

### `--help`

Each command's options, printed either way — nothing runs, no credentials read:

```bash
angel pr_review --help
angel help pr_review
```

```
usage: angel pr_review [options]

Review open pull requests labeled angel.

options:
  --dry-run   Print each review to stdout and make zero GitHub writes
  -h, --help  show this help message and exit
```

`angel --help`, a bare `help`, or no arguments lists the three commands instead, exit `0`
from each. An unknown command still exits `1` with `Unknown command: …`, whether `angel
bogus` or `angel help bogus`.

## Output and exit codes

A run prints three sections to stdout — what it's doing, what it produced, what it cost:

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

When nothing was due, `Reviews` holds `No pull requests to review` or `No issues to
review`; `Usage` still prints.

### The `Usage` section

Per-run total of every model call, summed from the same numbers the `model call completed`
log records carry — see [`LOGS.md`](LOGS.md) for per-call detail. Field names match those
records exactly:

| Field | Meaning |
|---|---|
| `calls` | how many times the model was called, `complete` and `completeStructured` together |
| `input_tokens` / `output_tokens` / `total_tokens` | summed across those calls; a provider that returns no usage metadata contributes `0` while still counting toward `calls` |
| `duration_ms` | wall time inside the provider calls, milliseconds — not the run's total wall time |

`chat` prints the same section at session end, and **before** a non-zero exit, so a failed
run still reports what it spent.

### Color

Colored when stdout is a terminal, plain otherwise. `ANGEL_COLOR` overrides either
direction; a non-empty `NO_COLOR` always wins. Only headings and status lines are styled —
review bodies never are.

### Failures

Each repository and item is isolated — a model error on the fifth of ten pull requests still
leaves the other nine reviewed and posted. What failed prints to stderr under its own
heading, one line each, plus a count:

```
Failures ───────────────────────────────────────────────────────────────

Failed review_pull_requests for owner/repo#12: HttpStatusError: 500 response from GET …
Failed post_review_comments for owner/other: TypeError: fetch failed
2 of 5 items failed
```

Repository-level failures (one of thirty unreachable during the scan) carry no item number,
printed as `owner/repo`. Failures go to stderr, the three sections above to stdout, so
`2> /dev/null` keeps the report and drops the errors.

| Exit code | Meaning |
|---|---|
| `0` | every item due for review was reviewed and posted (including the case where nothing was due) |
| `1` | at least one repository or item failed, or the command was invalid, or credentials were missing |

The non-zero exit is what a scheduler notices. Same failures appear as `WARNING` records in
the JSON log with structured `stage` / `error_type` fields — see [`LOGS.md`](LOGS.md) for
what every run writes to console and `log/`.

## Configuration

Copy `.env.example` to `.env` and fill in these variables.

| Variable | Needed by | Description |
|---|---|---|
| `ANGEL_NVIDIA_API_KEY` | all three commands | NVIDIA API key from https://build.nvidia.com — used for every model call. |
| `ANGEL_GITHUB_APP_ID` | `pr_review`, `issue_review` | ID of the GitHub App to authenticate as. |
| `ANGEL_GITHUB_PRIVATE_KEY_PATH` | `pr_review`, `issue_review` | Path to that App's private key (`.pem`). A leading `~/` is expanded. |
| `ANGEL_NVIDIA_MAX_COMPLETION_TOKENS` | optional, all three commands | Output tokens per model call, default `32768`. Counts reasoning as well as the answer, so sizing to the review text alone truncates the reply mid-object and fails the item. Non-integer or non-positive exits `1` rather than falling back to default. |
| `ANGEL_COLOR` | optional, all three commands | `auto` (default) colors only on a terminal; `always` keeps color when piping or redirecting; `never` disables it; unrecognised value = `auto`. Non-empty `NO_COLOR` disables color regardless. |

A missing *required* variable exits `1` with `<NAME> environment variable is not set.`
before any work starts. `.env` loads automatically, searched upward from the current
directory — run from the project root; an already-exported shell variable wins over the
file.

### The GitHub App

[kandy-angel](https://github.com/apps/kandy-angel) is the App behind the reviews — it
reviews exactly the repositories it's installed on, no list to maintain in code. Three
permissions only, so it cannot approve, merge, or push:

| Permission | Used for |
|---|---|
| **Pull requests: read** | listing PRs and fetching diffs |
| **Issues: read and write** | reading issues and comments, creating the `angel` label, posting the review comment |
| **Metadata: read** | required by the others |

## Testing

`npm run ci` runs the whole gate — `biome ci`, then `tsc --noEmit`, then `vitest run`:

```bash
npm run ci
npm run test:unit          # fakes only, fastest
npm run test:integration   # client code over recorded GitHub payloads
npm run coverage           # the same tests, with a coverage report
```

Neither suite touches the network. Split and fixture details in [`TESTING.md`](TESTING.md).
Same three checks run in GitHub Actions (`.github/workflows/ci.yml`) on every push and pull
request, Node 22 and 24.

## Known gaps

- **Nothing schedules a run.** Both review commands are one-shot; see [`TODO.md`](TODO.md),
  "Pick a deployment story".
- **The CLI has no scoping flags** — no `--version`, `--repo owner/name`, `--limit N`,
  `--log-level`, or `--log-file`. See "Finish the CLI flags".
- **Some failures still print a stack trace** rather than a message — a bad private-key path,
  an expired key, or Ctrl-C out of `chat`. See "Fail with a message, not a stack trace".
- **No rate-limit or backoff handling.** A run that hits GitHub's secondary limit fails the
  affected items instead of waiting.
</content>
