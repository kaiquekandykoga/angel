# Nishikihebi — TODO

Open work only. Goal: a Python/LangGraph service that is safe against untrusted input,
observable, resumable, deployable, and typed. When an item lands, delete it.

## Conventions (also: instructions for AI)

Item shape: `### <imperative title>` + **Where** / **Why** (concrete failure, not preference) /
**Do** / **Done when** (observable condition). Omit any line that adds nothing.

**P0** blocker for unattended running · **P1** required for production-ready · **P2** excellence.

Rules: one item = one deliverable; verify against the code before adding or deleting (an item is
done only when its *Done when* holds and `uv run ci` is green); promote on impact; keep it short —
non-actionable rationale belongs elsewhere in `docs/`.

New work comes from: real-run bugs, unused LangGraph capabilities (checkpointers, `Send`,
structured output, `interrupt`), unadopted Python/tooling practice, or operational gaps.

---

## P0

### Harden against prompt injection; validate output before posting
**Where:** `agents/*/prompts.py`, `agents/*/nodes.py`, `agents/_shared.py`
**Why:** attacker-controlled text (PR/issue bodies, comments, diffs) is interpolated undelimited,
and output is published under the App's identity. A crafted PR can post fabricated approval or
links signed `kandy-nishikihebi[bot]` on every watched repo.
**Do:** (1) fence untrusted fields (`<untrusted_pull_request_body>…`) and declare fenced content as
data, never instructions; (2) refusal clause — never follow reviewed-content instructions, claim
approval authority, or emit links absent from the diff; (3) validate before posting — length cap,
strip external links, reject non-review-shaped output (this is the layer that actually saves you);
(4) keep App permissions comments-only; (5) footer: "Automated review by nishikihebi — not a human
approval."
**Done when:** an injection fixture produces no policy-violating comment, enforced by a test on the
validation layer.

### Isolate per-item failures; add a retry policy
**Where:** `agents/{pr,issue}_review/nodes.py`, both `graph.py`
**Why:** all reviews are generated, then all posted. A model error on item 5 of 10 discards four
paid-for reviews; one GitHub 500 kills a 30-repo scan.
**Do:** per-item `try/except` with context logging, continue, record failures in state; add
`RetryPolicy(max_attempts=3)` on review nodes (LangGraph 1.2, unused today).
**Done when:** a fake client failing on item 3 of 5 still posts the other 4 and exits non-zero.

### Cap and filter the diff sent to the model
**Where:** `agents/pr_review/nodes.py`, `clients/github.py::fetch_diff`
**Why:** the full diff goes in with no cap or filter. A lockfile touch (this repo's `uv.lock` is
196 KB) blows the context window — a hard API error killing the run — and costs money otherwise.
**Do:** cap total diff bytes (~100 KB) and say so in the prompt when truncated; skip lockfiles,
`dist/`, minified assets, binaries, files over N KB; prefer tokens over bytes. `/pulls/{n}/files`
lets you drop whole files instead of truncating mid-hunk.
**Done when:** an oversized fixture diff is truncated with a marker rather than sent whole.

### Add `--dry-run`
**Where:** `__main__.py`, `agents/_shared.py::post_review_comments`
**Why:** no way to test against real repositories without commenting on them.
**Done when:** `nishikihebi pr_review --dry-run` prints reviews and makes zero write calls.

### Add a `LICENSE`
Without one the code is legally "all rights reserved". One file; highest signal-per-byte item here.
Reference it from `pyproject.toml` (`license`).

---

## P1

### Rate-limit and backoff handling (GitHub, NVIDIA)
**Where:** `clients/{github,llm}.py`
**Why:** `raise_for_status()` and nothing else. Production hits 403 + `x-ratelimit-remaining: 0`,
403/429 + `Retry-After` (comment loops trigger the secondary limit), routine 5xx, NVIDIA 429/503.
**Do:** `httpx.HTTPTransport(retries=3)` for connection-level, plus a response hook reading
`Retry-After` / `x-ratelimit-reset` and sleeping. `tenacity` is the usual backoff dependency.

### Expire and refresh installation tokens
**Where:** `clients/github.py::InstallationTokenProvider.tokens` (~71)
**Why:** tokens are cached per repo forever; GitHub installation tokens live 1 hour, so a long run
401s halfway through with no recovery.
**Do:** store `(token, expires_at)`, treat as expired ~5 min early, re-mint; invalidate and retry
once on any 401.

### Turn `settings.py` into real settings
**Where:** `settings.py`, `clients/llm.py:19–21`, `logs.py`
**Why:** `REVIEWER_LOGIN`, `LABEL`, `LABEL_COLOR`, `NVIDIA_*`, and the log directory are scattered
module constants. `REVIEWER_LOGIN = "kandy-nishikihebi[bot]"` hardcodes *your* App — nobody else
can run this without editing source.
**Do:** a `pydantic-settings` model with env overrides and startup validation; fold in every
remaining constant so each knob has one documented place.

### Accept private key material, not just a path
**Where:** `clients/github.py`, `env.py`
**Why:** `NISHIKIHEBI_GITHUB_PRIVATE_KEY_PATH` is path-only; containers and secrets managers hand
you material, not a file — a hard blocker for containerised deployment.
**Do:** support `NISHIKIHEBI_GITHUB_PRIVATE_KEY` (raw or base64); warn if the `.pem` is
group/world-readable; load `.env` once at startup from a known location — `env.py` calls
`load_dotenv(find_dotenv(usecwd=True))` per lookup and `usecwd=True` walks *up*, so running from a
subdirectory of an unrelated project can pick up a stranger's `.env`.

### Enable LangSmith tracing
`langsmith` is already installed transitively; `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` /
`LANGSMITH_PROJECT` give full capture of every run, node, and prompt/response — today a bad review
leaves only JSON logs of *lengths*. Highest value-per-effort item in the file.

### Log JSON to stdout by default
**Where:** `logs.py`
**Why:** `configure_logging` writes `log/nishikihebi-<timestamp>.jsonl` relative to cwd, so log
location depends on invocation directory. No rotation, no retention, one file per run — hourly
scheduling means 8,760 files a year.
**Do:** 12-factor it — JSON to stdout, file handler behind an opt-in `--log-file`; add a run-id and
`exc_info` to every record (no traceback is logged anywhere today).
**Also:** stop logging whole review bodies at DEBUG (`agents/*/nodes.py`) — model output derived
from untrusted input lands on disk unbounded. Log a hash and length; full bodies only behind
`--verbose`, with a redaction filter in front.

### Pick a deployment story
**Why:** `pr_review` is a one-shot CLI invoked by hand; nothing schedules, restarts, or alerts.
**Do:** either scheduled (container + cron/systemd timer or scheduled GH Actions — simplest;
latency is the poll interval) or webhook-driven (HTTP service on `pull_request`/`issues`/`label`
with `X-Hub-Signature-256` verification). Webhooks are what App auth is *for* — you already have it
and are merely polling — and they mostly dissolve the freshness heuristics. Either way add a
`Dockerfile` (~15 lines on `ghcr.io/astral-sh/uv` with `uv.lock`).

### Make `ensure_label` opt-in
**Where:** `agents/{issue,pr}_review/nodes.py:24`
**Why:** the label is created in every repo on every run — two wasted calls per repo per run, and
installing the App to review *one* repo silently adds a pink label to all of them, a least-surprise
violation that gets Apps uninstalled in orgs.
**Do:** `--ensure-label` or a one-shot `nishikihebi setup`; otherwise treat "no label" as "nothing
to review here".

### Replace the hand-rolled CLI
**Where:** `__main__.py`
**Why:** `main()` is `if len(argv) != 1 or argv[0] not in COMMANDS`. No `--help`, no `--version`,
no flags.
**Do:** `argparse` or `typer`, then add `--dry-run` (P0), `--repo owner/name`, `--limit N`,
`--log-level`, `--log-file`, `--version`.

### Exit non-zero on partial failure
Nothing emits reviews-posted / items-skipped / API-errors / tokens-used anywhere a dashboard can
read. A non-zero exit at least makes the scheduler's failure notification do the alerting for free.

### Re-review a PR on its pushed head, not its commit date
**Where:** `agents/pr_review/nodes.py:41-46`, `clients/github.py::fetch_commit_date` (185)
**Why:** freshness is `fetch_commit_date(head_sha) > last_review`, but that is the git *committer*
date baked into the commit, not push time. Commit Monday, reviewed Wednesday, pushed Friday → the
head's date predates the last review and the PR is silently never reviewed again; force-pushing to
an earlier commit fails the same way. This loses work rather than wasting a call.
**Do:** record the reviewed `head_sha` in the bot's own comment (`<!-- nishikihebi: sha=… -->`) and
re-review when the current head differs — same marker as the issue-heuristic item, and it drops
`fetch_commit_date` (one call per PR per run) entirely.
**Done when:** a fixture PR whose head commit date precedes the bot's last comment, but whose
`head_sha` differs from the recorded one, is selected for review.

### Add security tooling
**Where:** `pyproject.toml`, `__ci__.py`
**Do:** add `S` (flake8-bandit) to ruff `select`; add `pip-audit` (or uv's audit path) to `CHECKS`;
enable Dependabot or Renovate for the lockfile.

---

## P2

### Build an eval harness for review quality
**Why:** all 99 tests assert plumbing; zero assert review quality — so the prompt, the component
with the most influence on whether this is good, is the only one with no regression protection.
**Do:** 10–20 fixture PRs/issues with known findings (planted bug, missing test, ambiguous
requirement) and an LLM-as-judge rubric (found it? specific? hallucinated files?). Run via
`pytest -m eval`, excluded by default — costs money, nondeterministic. Hallucinated file/line
citations are checkable mechanically, no judge needed.

### `Send` fan-out and async
Reviews run strictly sequentially. `Send` gives per-item parallelism, retry, and failure isolation
in one move; `ainvoke` + `httpx.AsyncClient` matter once fan-out exists.

### Durable checkpointer on the review graphs
`build_pr_review_graph` compiles without one, so a mid-run crash loses everything and there is no
resume — `SqliteSaver` locally, `PostgresSaver` deployed. Durable execution is the main reason to
be on LangGraph at all. Chat uses `MemorySaver`, so conversations die with the process;
`SqliteSaver` + `--thread-id` makes them resumable cheaply.

### Structured output for reviews
`cast("str", ai_message.content)` is trusted blindly. `.with_structured_output(ReviewSchema)` gives
summary/severity/per-file findings, letting you render the comment, enforce length, and drop
disallowed links (the P0 validation layer) without touching the prompt.

### Streaming chat REPL
`session.ask()` blocks for the full reply. `graph.stream(..., stream_mode="messages")` — small
change, biggest perceived-quality delta here.

### `langgraph.json` for LangGraph Studio
~10 lines unlocking `langgraph dev` → visual stepping, high value for a project whose
`docs/GRAPHS.md` hand-draws ASCII. Needs real work: it wants module-level `graph` objects, but
`build_*_graph` takes credentialed clients, so a bare `graph = build_pr_review_graph(...)` fails at
import without `.env`. Keep the factories; add a guarded Studio entry point.

### Token and cost accounting
Nothing records tokens or dollars for a bot reading unbounded diffs across unbounded repos. Log
`response.usage_metadata` per call, aggregate per run, consider a budget ceiling that aborts cleanly.

### Version the prompts
Prompts are diffable in `agents/<name>/prompts.py` but unversioned — no constant, no changelog, no
A/B path. Add a version constant per prompt and log it per run so a trace ties back to its prompt.

### Make model choice configurable
`NVIDIA_MODEL` is a module constant; silent model swaps are a leading cause of "it used to work".
Make it configurable, log it per run, pin it. `NVIDIA_MAX_COMPLETION_TOKENS = 1024` is low for a
thorough review and truncates mid-sentence on large diffs — raise it for the review path.

### Fix the listing inefficiencies
- `list_open_pull_requests` filters by label client-side (github.py:171) while `list_open_issues`
  filters server-side — inconsistent, and the PR path downloads far more than it needs.
- The whole repo loop could be one `GET /search/issues?q=is:open+label:nishikihebi+is:pr` instead
  of 2 + 2N requests. Worth it past a handful of repos.
- `fetch_commit_date` is an extra call per PR per run. Don't swap it for `updated_at` — that bumps
  on any comment. The P1 head-sha item removes the call outright.

### Replace the issue freshness heuristic
`issue.updated_at > last_review` re-fires on any mutation — label, assignment, reaction — costing a
model call to say nothing new, and it depends on the bot's own comment not bumping `updated_at`
past its own `created_at`, an undocumented GitHub timing detail.
**Do:** record what was actually reviewed — a content hash, or a marker in the bot's own comment
(`<!-- nishikihebi: sha=… -->`). Most review bots use the marker: it keeps state in the only place
guaranteed to survive, the issue itself.

### Human-in-the-loop approval
`interrupt()` gives a `--require-approval` mode pausing before posting — genuinely useful for a bot
commenting publicly under your identity.

### Fail with a message, not a traceback
**Where:** `__main__.py:64-75`, `agents/chat/repl.py:35-39`
**Why:** `main()` catches only `MissingApiKeyError` and `MissingGitHubCredentialsError`. A typo in
`NISHIKIHEBI_GITHUB_PRIVATE_KEY_PATH` isn't a missing variable, so `build_github_client`
(github.py:249) raises bare `FileNotFoundError`; an expired key gives `httpx.HTTPStatusError`. Both
print a stack trace. `repl.run` catches `EOFError` but not `KeyboardInterrupt`, so Ctrl-C out of
`chat` — the documented sibling of Ctrl-D — also tracebacks.
**Do:** one `try/except` in `main()` for `OSError` / `httpx.HTTPStatusError` / `KeyboardInterrupt`,
logging with `exc_info` and exiting via `sys.exit(message)`; catch `KeyboardInterrupt` alongside
`EOFError` in `repl.run`.
**Done when:** a missing private-key file exits with a one-line message and no traceback, and
Ctrl-C in the REPL returns cleanly.

### Close the `httpx.Client`
`build_github_client` (github.py:233) creates a client nobody closes — harmless for a short-lived
CLI, a leak in anything long-running, and a `ResourceWarning` once warnings are enabled in tests.

### Typing and lint strictness
- Node factories annotate parameters but not returns (`def call_llm(client: LlmClient):`,
  `def post_review_comments(github: GitHubClient):`); the closure's type is inferred and
  `post_review_comments`'s node returns bare `dict`. basedpyright at `standard` permits this — move
  toward `strict` (or ruff `ANN`) and declare `Callable[[State], dict[...]]` returns.
- f-strings in log calls defeat lazy formatting and lose the structured argument, while
  `extra={"context": {...}}` is already used elsewhere — an internal inconsistency.
- Ruff has no `target-version`, no `line-length`. Consider `ANN`, `TRY`, `LOG`/`G`, `PTH`, `ARG`,
  `DTZ`, `ERA`, `A`.
- `__ci__.py`'s `CHECKS` runs `ruff check`, `basedpyright`, `pytest` — no `ruff format --check`.
  Since `uv run ci` is deliberately the only gate, formatting is the one thing nothing enforces.

### Packaging and repo polish
- **Rename `__ci__.py`** — dunder names are conventionally the runtime's (`__main__`, `__init__`).
  `tasks.py`, `scripts/ci.py`, or a `Makefile`/`justfile` target is expected.
- **Thin `pyproject.toml` metadata** — no `license`, `classifiers`, `[project.urls]`, keywords.
- **Static `0.1.0`** with no tags, no `CHANGELOG.md`, no `--version`. Pick SemVer or CalVer and tag.
- **Inaccurate description** — "Multi-Agent System using Python" is three linear single-agent
  graphs. Fix it, or build toward it (a planner/critic split would be genuine multi-agent).
- **No `py.typed`** — one empty file; only matters if something imports this as a library.
- **`requires-python = ">=3.14"`** constrains base images, some wheels, and contributors. Fine for
  a personal project — just make it a documented decision.
- **No `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, or issue/PR templates** — only matters with
  contributors, but evaluators check first.
- **Document the local-CI decision in `docs/USAGE.md`.** `.github/workflows/` is deliberately
  absent (removed in `2c27db5`); writing it down is the difference between a decision and an
  omission — and note that a second contributor ends "green on my machine".
- **No limitations section in `README.md`.** `GRAPHS.md`, `LOGS.md`, and `USAGE.md` each carry a
  "Known gaps"; the entry point doesn't, so a reader opens three files to learn there are no
  retries and no rate-limit handling. Add a short one, plus a LICENSE badge.
