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
stop. Nothing schedules them yet. See [`TODO.md`](TODO.md) — "Pick a deployment story" for
the scheduling options, and "Add `--dry-run`" / "Replace the hand-rolled CLI" for the flags
that are still missing: there is currently no way to see what a review run *would* post
without posting it.

What each run writes to the console and to disk is documented in [`LOGS.md`](LOGS.md).

### Exit codes

A review run isolates each repository and each item, so one failure never discards the rest
of the work — a model error on the fifth pull request still leaves the other nine reviewed
and posted. What failed is then reported and the run exits non-zero, which is what makes a
scheduler notice:

| Exit code | Meaning |
|---|---|
| `0` | every item that was due for review was reviewed and posted (including the case where nothing was due) |
| `1` | at least one repository or item failed, or the command was invalid, or credentials were missing |

Failures print to stderr, one line each, followed by a count:

```
Failed review_pull_requests for owner/repo#12: HTTPStatusError: 500 Server Error
Failed post_review_comments for owner/other: TimeoutError:
2 of 5 items failed
```

Repository-level failures — one repository of thirty unreachable during the scan — carry no
item number and print as `owner/repo`. The same failures appear as `WARNING` records in the
JSON log with structured `stage` / `error_type` fields; see [`LOGS.md`](LOGS.md).

## Testing

`uv run ci` runs the whole suite. The tests are split in two:

| Tree | What lives there | How it stubs the world |
|---|---|---|
| `tests/unit_tests/` | Graphs, nodes, the REPL, logging, the CLI — everything driven through a fake. | `FakeGitHubClient` / `FakeClient` from `tests/conftest.py`. No HTTP at all. |
| `tests/integration_tests/` | `HttpGitHubClient` and `InstallationTokenProvider` — the code that actually speaks HTTP. | [`respx`](https://lundberg.github.io/respx/) routes serving recorded GitHub payloads from `tests/fixtures/`. Still no network. |

```bash
uv run pytest -m "not integration"   # fakes only, fastest
uv run pytest -m integration         # client code over recorded payloads
```

Everything under `tests/integration_tests/` is marked `integration` automatically by that
tree's `conftest.py` — you do not mark tests by hand.

**Why both.** `FakeGitHubClient` encodes the same assumptions as the real client, so it can
never falsify them; that is exactly how the missing pagination went unnoticed. The recorded
fixtures are full-shape GitHub responses (every field the API really returns, sanitized),
so a test can serve a `Link: rel="next"` header and prove that page 2 is dropped.

**Adding a fixture.** Drop the sanitized JSON (or raw text, for diffs) under
`tests/fixtures/github/` and load it with the `load_fixture` fixture:

```python
def test_something(load_fixture):
    payload = load_fixture("github/pulls_page1.json")
```

Keep the whole response shape rather than the handful of fields the client reads today —
the extra fields are what makes the fixture useful when the client grows. Never commit a
real token: the recorded installation token is a redacted placeholder.

Some integration tests are `xfail(strict=True)` and name an open item in [`TODO.md`](TODO.md).
That is deliberate — they document a known bug against real payloads. When the fix lands,
the test starts passing and the marker gets deleted in the same PR.
