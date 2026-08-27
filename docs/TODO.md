# Angel — TODO

Open work only. Goal: a TypeScript/LangGraph service that is safe against untrusted input,
observable, resumable, deployable, and typed. When an item lands, delete it.

## Conventions (also: instructions for AI)

Item shape: `### <imperative title>` + **Where** / **Why** (concrete failure, not
preference) / **Do** / **Done when** (observable condition). Omit any line that adds
nothing.

**P0** blocker for unattended running · **P1** required for production-ready · **P2**
excellence.

Rules: one item = one deliverable; verify against the code before adding or deleting (an
item is done only when its *Done when* holds and `npm run ci` is green); promote on impact;
keep it short — non-actionable rationale belongs elsewhere in `docs/`.

New work comes from: real-run bugs, unused LangGraph capabilities (checkpointers, `Send`,
structured output, `interrupt`), unadopted TypeScript/tooling practice, or operational gaps.

---

## P0

### Harden against prompt injection; validate output before posting
**Where:** `agents/*/prompts.ts`, `agents/*/nodes.ts`, `agents/shared.ts`
**Why:** attacker-controlled text (PR/issue bodies, comments, diffs) is interpolated
undelimited, and output is published under the App's identity. A crafted PR can post
fabricated approval or links signed `kandy-angel[bot]` on every watched repo.
**Do:** (1) fence untrusted fields (`<untrusted_pull_request_body>…`) and declare fenced
content as data, never instructions; (2) refusal clause — never follow reviewed-content
instructions, claim approval authority, or emit links absent from the diff; (3) validate
before posting — reviews now arrive as `PullRequestReviewOutput` / `IssueReviewOutput`, so
the shape check is done; enforce the length cap and strip external links in the renderers
(the layer that actually saves you); (4) keep App permissions comments-only; (5) footer:
"Automated review by angel — not a human approval."
**Done when:** an injection fixture produces no policy-violating comment, enforced by a test
on the validation layer.

### Cap and filter the diff sent to the model
**Where:** `agents/pr-review/nodes.ts`, `clients/github.ts::fetchDiff`
**Why:** the full diff goes in with no cap or filter. A lockfile touch (this repo's
`package-lock.json` is hundreds of KB) blows the context window — a hard API error killing
the run — and costs money otherwise.
**Do:** cap total diff bytes (~100 KB) and say so in the prompt when truncated; skip
lockfiles, `dist/`, minified assets, binaries, files over N KB; prefer tokens over bytes.
`/pulls/{n}/files` lets you drop whole files instead of truncating mid-hunk.
**Done when:** an oversized fixture diff is truncated with a marker rather than sent whole.

---

## P1

### Add a verification judge node to `pr_review`
**Where:** `agents/pr-review/{graph,nodes,prompts,state}.ts`
**Why:** repeated runs over the same PR return different reviews. Temperature is pinned at
`0` and the three lens prompts narrow the mandate, but nothing checks a finding against the
diff before it's published — a finding citing a file or line the diff never touched, or
restating something already in the comments, still gets posted under the App's identity.
**Do:** a `verify_findings` node between `review_pull_requests` and `post_review_comments`.
Give the model the diff plus the merged findings and have it return, per finding, keep/drop
with a reason; drop anything unsupported. Cite-checking is mechanical first — a finding
whose `file` is absent from the diff, or whose `line` falls outside the touched hunks, can
be dropped without a model call, so do that pass before spending a call.
**Done when:** a fixture review carrying one finding that cites a file absent from the diff
posts a body without it, and the drop is logged with the reason.

### Rate-limit and backoff handling (GitHub, NVIDIA)
**Where:** `clients/{github,http,llm}.ts`
**Why:** `ensureOk()` and nothing else. Production hits 403 + `x-ratelimit-remaining: 0`,
403/429 + `Retry-After` (comment loops trigger the secondary limit), routine 5xx, NVIDIA
429/503. A pull request review is also three long non-streaming calls — one per lens — so a
timeout at `NVIDIA_TIMEOUT_MS` on any one loses the whole item with no second attempt, and
the two lenses already paid for are thrown away.
**Do:** a retry wrapper in `HttpClient.request` reading `Retry-After` / `x-ratelimit-reset`
and sleeping, with jittered backoff on connection errors and 5xx; the same for the model
client.
**Done when:** a fixture serving 429 + `Retry-After: 0` then 200 completes the call, and the
wait is logged.

### Expire and refresh installation tokens
**Where:** `clients/github.ts::InstallationTokenProvider.tokens`
**Why:** tokens are cached per repo forever; GitHub installation tokens live 1 hour, so a
long run 401s halfway through with no recovery.
**Do:** store `{ token, expiresAt }` — `/access_tokens` already returns `expires_at`, which
the provider currently drops — treat as expired ~5 min early, re-mint; invalidate and retry
once on any 401.

### Turn `settings.ts` into real settings
**Where:** `settings.ts`, `clients/llm.ts`, `logs.ts`
**Why:** `REVIEWER_LOGIN`, `LABEL`, `LABEL_COLOR`, `NVIDIA_*`, and the log directory are
scattered module constants. `REVIEWER_LOGIN = "kandy-angel[bot]"` hardcodes *your* App —
nobody else can run this without editing source.
**Do:** one zod-validated settings object parsed from the environment at startup; fold in
every remaining constant so each knob has one documented place, and fail with the field path
when a value is wrong.

### Accept private key material, not just a path
**Where:** `clients/github.ts`, `env.ts`
**Why:** `ANGEL_GITHUB_PRIVATE_KEY_PATH` is path-only; containers and secrets managers hand
you material, not a file — a hard blocker for containerised deployment.
**Do:** support `ANGEL_GITHUB_PRIVATE_KEY` (raw or base64); warn if the `.pem` is
group/world-readable; load `.env` once at startup from a known location — `env.ts` walks
*up* from the cwd, so running from a subdirectory of an unrelated project can pick up a
stranger's `.env`.

### Enable LangSmith tracing
`langsmith` is already installed transitively; `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` /
`LANGSMITH_PROJECT` give full capture of every run, node, and prompt/response — today a bad
review leaves only JSON logs of *lengths*. Highest value-per-effort item in the file.

### Log JSON to stdout by default
**Where:** `logs.ts`
**Why:** `configureLogging` writes `log/angel-<timestamp>.jsonl` relative to cwd, so log
location depends on invocation directory. No rotation, no retention, one file per run —
hourly scheduling means 8,760 files a year. Records are written with `appendFileSync`, one
syscall each.
**Do:** 12-factor it — JSON to stdout, file handler behind an opt-in `--log-file`; add a
run-id and error stacks to every record (no stack trace is logged anywhere today); buffer
the file writes.
**Also:** stop logging whole review bodies at DEBUG (`agents/shared.ts::logReviewProduced`,
the single site for both review nodes) — model output derived from untrusted input lands on
disk unbounded. Log a hash and length; full bodies only behind `--verbose`, with a redaction
filter in front.

### Pick a deployment story
**Why:** `pr_review` is a one-shot CLI invoked by hand; nothing schedules, restarts, or
alerts.
**Do:** either scheduled (container + cron/systemd timer or scheduled GH Actions —
simplest; latency is the poll interval) or webhook-driven (HTTP service on
`pull_request`/`issues`/`label` with `X-Hub-Signature-256` verification). Webhooks are what
App auth is *for* — you already have it and are merely polling — and they mostly dissolve
the freshness heuristics. Either way add a `Dockerfile` (multi-stage: `npm ci` + `npm run
build`, then `npm ci --omit=dev` into a `node:22-slim` runtime).

### Make `ensureLabel` opt-in
**Where:** `agents/{issue,pr}-review/nodes.ts`
**Why:** the label is created in every repo on every run — two wasted calls per repo per
run, and installing the App to review *one* repo silently adds a pink label to all of them,
a least-surprise violation that gets Apps uninstalled in orgs.
**Do:** `--ensure-label` or a one-shot `angel setup`; otherwise treat "no label" as "nothing
to review here".

### Finish the CLI flags
**Where:** `cli.ts`, `main.ts`
**Why:** the parser handles subcommands, `--help`, `help <command>`, and `--dry-run` — but a
run is still all-or-nothing: no way to target one repository, cap the work, or redirect the
log, and no `--version` to put in a bug report.
**Do:** add `--repo owner/name`, `--limit N`, `--log-level`, `--log-file`, and `--version`
(read from `package.json`), threading the scoping ones into the graph state.

### Emit run metrics
Partial failures now exit non-zero, so a scheduler alerts for free — but nothing emits
reviews-posted / items-skipped / API-errors / tokens-used anywhere a dashboard can read.

### Add supply-chain tooling
**Where:** `.github/workflows/`, `package.json`
**Done:** `.github/dependabot.yml` watches `package-lock.json` and the workflow actions
weekly, grouped so a week's bumps land as a few pull requests.
**Do:** add `npm audit --audit-level=high` to the CI job; pin the actions by SHA (Dependabot
updates pinned SHAs too).

---

## P2

### Build an eval harness for review quality
**Why:** every test asserts plumbing; zero assert review quality — so the prompt, the
component with the most influence on whether this is good, is the only one with no
regression protection.
**Do:** 10–20 fixture PRs/issues with known findings (planted bug, missing test, ambiguous
requirement) and an LLM-as-judge rubric (found it? specific? hallucinated files?). Put them
under `tests/eval/`, excluded from the default `vitest run` — they cost money and are
nondeterministic. Hallucinated file/line citations are checkable mechanically, no judge
needed. Sampling is pinned at `temperature=0` (`clients/llm.ts`), so run-to-run drift is now
the prompt's, not the sampler's — the harness measures whether a prompt change helped rather
than whether the dice fell differently.

### `Send` fan-out and concurrency
Reviews run strictly sequentially — every `await` in the fetch and review loops is serial,
even though nothing shares state between items. Failures are already isolated per item, but
`retryPolicy` is node-granular, so a single flaky review cannot be retried without
re-running the whole node. `Send` gives per-item parallelism *and* per-item retry in one
move; a bounded concurrency limit matters the moment fan-out exists.

### Durable checkpointer on the review graphs
`buildPrReviewGraph` compiles without one, so a mid-run crash loses everything and there's
no resume — `@langchain/langgraph-checkpoint-sqlite` locally, `-postgres` deployed. Durable
execution is the main reason to be on LangGraph at all. Chat uses `MemorySaver`, so
conversations die with the process; SQLite + `--thread-id` makes them resumable cheaply.

### Streaming chat REPL
`session.ask()` blocks for the full reply. `graph.stream(..., { streamMode: "messages" })` —
small change, biggest perceived-quality delta here.

### `langgraph.json` for LangGraph Studio
~10 lines unlocking `langgraphjs dev` → visual stepping, high value for a project whose
`docs/GRAPHS.md` hand-draws ASCII. Needs real work: it wants module-level `graph` exports,
but `build*Graph` takes credentialed clients, so a bare `export const graph =
buildPrReviewGraph(...)` fails at import without `.env`. Keep the factories; add a guarded
Studio entry point.

### Dollar cost and a budget ceiling
**Where:** `clients/llm.ts`
**Why:** a run now reports its own token total (`usageTotals()`, printed as the `Usage`
section), but a bot reading unbounded diffs across unbounded repos still has no dollar
figure and nothing that stops it — the tally counts spend, it does not cap it.
**Do:** dollars once there's a pricing source worth trusting for the configured model; a
budget ceiling checked against the running tally that aborts cleanly when crossed.
**Done when:** a run that exceeds the ceiling stops instead of spending past it.

### Version the prompts
Prompts are diffable in `agents/<name>/prompts.ts` but unversioned — no constant, no
changelog, no A/B path. Add a version constant per prompt and log it per run so a trace ties
back to its prompt.

### Make model choice configurable
`NVIDIA_MODEL` is a module constant; silent model swaps are a leading cause of "it used to
work". Make it configurable, log it per run, pin it — the completion ceiling next to it
already reads from the environment, so follow that shape.

### Validate GitHub payloads at the boundary
**Where:** `clients/http.ts::HttpResponse.json`, `clients/github.ts`
**Why:** `json<T>()` casts; the `Api*` interfaces describe what GitHub is believed to return
and nothing checks it. A renamed or missing field surfaces as `undefined` deep in a node
rather than as an error naming the endpoint.
**Do:** parse each list payload through a narrow zod schema at the client boundary, keeping
the schemas permissive about extra fields.

### Fix the listing inefficiencies
- `listOpenPullRequests` filters by label client-side while `listOpenIssues` filters
  server-side — inconsistent, and the PR path downloads far more than it needs.
- The whole repo loop could be one `GET /search/issues?q=is:open+label:angel+is:pr` instead
  of 2 + 2N requests. Worth it past a handful of repos.
- `listComments` is one call per labeled PR per run, made before the freshness check can
  skip it. The search endpoint above cannot replace it — the head-sha marker lives in the
  comment bodies.

### Replace the issue freshness heuristic
`issue.updatedAt > lastReview` re-fires on any mutation — label, assignment, reaction —
costing a model call to say nothing new, and it depends on the bot's own comment not
bumping `updated_at` past its own `created_at`, an undocumented GitHub timing detail.
**Do:** record what was actually reviewed in the bot's own comment, reusing `reviewMarker` /
`reviewedSha` in `agents/shared.ts` — the marker the PR path already writes. Issues have no
head sha, so the recorded value is a hash of the reviewed title + body + comment bodies.

### De-duplicate the pr-review/issue-review node pairs
**Where:** `agents/pr-review/nodes.ts`, `agents/issue-review/nodes.ts`
**Why:** `fetchPullRequests`/`fetchIssues` and `reviewPullRequests`/`reviewIssues` are ~90%
identical line-for-line — same nesting, logging shape, and failure bookkeeping, differing
only in field names and the freshness check. Any fix to error handling or logging has to be
made twice and can silently drift (the two freshness checks already diverge more than the
domain requires).
**Do:** extract the shared shape into a generic `fetchLabeledItems` / `reviewItems` helper
parameterized by small per-agent functions (list call, freshness predicate, prompt
renderer), keeping PR- and issue-specific bits injected rather than copy-pasted.
**Done when:** the fetch/review control flow exists once, with PR- and issue-specific
behavior isolated to injected functions, and both agents' existing tests pass unchanged in
intent.

### Human-in-the-loop approval
`interrupt()` gives a `--require-approval` mode pausing before posting — genuinely useful
for a bot commenting publicly under your identity.

### Fail with a message, not a stack trace
**Where:** `main.ts::buildClients`, `agents/chat/repl.ts`
**Why:** `main()` maps only `MissingApiKeyError`, `InvalidMaxCompletionTokensError`, and
`MissingGitHubCredentialsError` to an exit message. A typo in
`ANGEL_GITHUB_PRIVATE_KEY_PATH` isn't a missing variable, so `buildGithubClient` throws a
bare `ENOENT`; an expired key gives an `HttpStatusError`. Both print a stack trace. The REPL
returns cleanly at end of input but has no `SIGINT` handling, so Ctrl-C out of `chat` — the
documented sibling of Ctrl-D — kills the process mid-run.
**Do:** one `catch` in `start()` mapping `NodeJS.ErrnoException` / `HttpStatusError` to an
`ExitError` with a one-line message, logging the stack at `ERROR`; handle `SIGINT` in
`repl.run`.
**Done when:** a missing private-key file exits with a one-line message and no stack trace,
and Ctrl-C in the REPL returns cleanly.

### Typing and lint strictness
- Node factories annotate their returned function's state and result, but the factories
  themselves have inferred return types; declaring them makes the node contract explicit at
  the call site.
- Biome's type-aware rules are limited compared to `typescript-eslint`'s
  `strictTypeChecked` — weigh adding the latter alongside Biome for the rules that need the
  type checker (`no-unnecessary-condition`, `no-unsafe-argument`, exhaustive switch).
- Template literals in log messages (`` log.info(`reviewed ${repo}#${n}`) ``) duplicate
  what the context object already carries structurally — an internal inconsistency.

### Packaging and repo polish
- **Static `0.1.0`** with no tags, no `CHANGELOG.md`, no `--version`. Pick SemVer or CalVer
  and tag.
- **Not published** — `package.json` has `bin`, `files`, and `exports`-worthy metadata, but
  nothing is on npm and there's no release workflow.
- **No `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, or issue/PR templates** — only matters with
  contributors, but evaluators check first.
- **No `SECURITY.md`** — a bot that posts under a GitHub App identity should say where to
  report.
- **No coverage gate.** `npm run coverage` reports but nothing fails on a drop.
</content>
