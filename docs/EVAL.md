# Eval

`npm run eval` runs the review agents over a fixed dataset, scores every review with
deterministic code — no judge model — and sends the run to
[Langfuse](https://langfuse.com) as an experiment.

```bash
npm run eval:up                  # start the local Langfuse (once)
npm run eval                     # both agents
npm run eval -- pr_review        # one of pr_review, issue_review
```

It costs real model calls: three per pull request case (one per lens) and one per issue
case. Nothing is posted to GitHub — the graph's `post_review_comments` node writes into an
in-memory repository.

- [What a run does](#what-a-run-does) · [The scores](#the-scores) · [Adding a case](#adding-a-case)
- [The local Langfuse](#the-local-langfuse) · [Configuration](#configuration) · [Files](#files)

## What a run does

```
eval/datasets.ts        one item per case: input, expectedOutput, metadata
        │
        ▼
langfuse.experiment.run  one trace per item ("experiment-item-run")
        │
        ├── task ──────► eval/tasks.ts
        │                  StaticGitHubClient  the case, as a one-repository GitHub
        │                  RecordingLlmClient  the real model, keeping every structured reply
        │                  buildPrReviewGraph(...).invoke({}, { callbacks: [CallbackHandler] })
        │                                                       └─ every node and model call
        │                                                          becomes a Langfuse span
        │
        └── evaluators ─► eval/scorers.ts → scores attached to that item's trace
```

The task runs the **real graph**, not a stripped-down copy of it, so a change to a node, a
prompt, or the renderer shows up in the scores. The two seams that make that possible are
`StaticGitHubClient` (a `GitHubClient` serving one case's pull request or issue) and
`RecordingLlmClient` (a `LlmClient` decorator that keeps each structured reply, so the
scorers see the `Finding` objects the node produced rather than parsing markdown back out).

Item failures do not stop the run: Langfuse logs and skips the item, and the runner exits
`1` after reporting how many were lost.

## The scores

Every score is a plain function of the review and the diff. A score is **omitted** rather
than forced to `1` when a case gives it nothing to check — a review that cites no file at
all gets no `cited_files_in_diff`, so the averages stay honest.

| Score | Agent | Value |
|---|---|---|
| `cited_files_in_diff` | `pr_review` | Fraction of cited file paths the diff actually touches. The hallucination check. |
| `cited_lines_in_hunks` | `pr_review` | Fraction of cited lines that fall inside a changed hunk of the file they name. |
| `expected_files_flagged` | `pr_review` | Fraction of the case's expected files some finding cites. Recall of the planted bug. |
| `expected_keywords_mentioned` | both | Fraction of the case's expected keywords present in the rendered review, lowercased substring match — so `reproduc` matches every inflection. |
| `lenses_covered` | `pr_review` | Fraction of the three lenses with a `### <lens>` section in the posted body. |
| `acceptance_criteria_count` | `issue_review` | How many acceptance criteria were proposed. |
| `suggested_approach_present` | `issue_review` | `1` when the approach is non-blank. |
| `finding_count` | both | How many findings the review carried. Not a pass/fail — a drift signal. |

Keyword recall is crude on purpose: it is the part of "did it find the planted bug" that a
computer can settle. Judging *specificity* still needs a model, and that is the next item in
[`TODO.md`](TODO.md).

## Adding a case

Append to `PR_REVIEW_ITEMS` or `ISSUE_REVIEW_ITEMS` in `eval/datasets.ts`:

```ts
{
  metadata: { case: "dropped-await" },
  input: { repository, number, title, body, headSha, diff, comments },
  expectedOutput: {
    files: ["src/queue.ts"],   // paths a good review cites — must be paths the diff touches
    keywords: ["await"],       // lowercase stems the review should contain
  },
}
```

`tests/eval/datasets.test.ts` enforces both rules — an expected file the diff never touches,
or an uppercase keyword, fails `npm run ci` rather than quietly scoring `0` forever. Write
the diff with real `@@` headers: `cited_lines_in_hunks` parses them.

## The local Langfuse

A run reports to `http://localhost:3000` by default — the Langfuse that
[`eval/docker-compose.yml`](../eval/docker-compose.yml) brings up. Nothing leaves the
machine, and no account is needed.

```bash
npm run eval:up      # pull and start; waits until the API answers, minutes on a cold pull
npm run eval:logs    # follow every container
npm run eval:down    # stop, keeping the traces
npm run eval:reset   # stop and delete the volumes — every trace and score with them
```

The stack is Langfuse's own, trimmed: `langfuse-web` and `langfuse-worker` over Postgres,
ClickHouse, Redis, and MinIO. Only `langfuse-web` is published, on `127.0.0.1:3000`; the
five backing services talk over the compose network and bind no host port, so the stack
cannot collide with a Postgres or Redis already running on the machine.

`LANGFUSE_INIT_*` seeds the organisation, the project, its API keys, and a login on the
first boot, so a run needs no clicking through the UI. Sign in at
[localhost:3000](http://localhost:3000) with `dev@angel.local` / `angel-local-dev` to read
the traces. Those credentials, and the `pk-lf-angel-local` / `sk-lf-angel-local` project
keys that `eval/langfuse.ts` falls back to, are development constants committed on purpose
— they secure a stack reachable only from localhost. Never reuse them anywhere else.

## Configuration

Three variables beyond the ones in [`USAGE.md`](USAGE.md#configuration), all optional:
`LANGFUSE_PUBLIC_KEY` (`pk-lf-…`), `LANGFUSE_SECRET_KEY` (`sk-lf-…`), and
`LANGFUSE_BASE_URL`.

| What is set | Where the run reports |
|---|---|
| Nothing | The local stack above — `http://localhost:3000` with the seeded keys. |
| Both keys | That project, at `LANGFUSE_BASE_URL` if set — a [cloud.langfuse.com](https://cloud.langfuse.com) project, or another instance. |
| One key, or a base URL other than the local one with no keys | Nothing: exits `1` with a one-line message before any model call. Keys are only ever filled in for the local default. |

Spans are exported immediately rather than batched, so a short run cannot lose its trace on
exit. The run prints the instance it reported to as its first line.

## Files

| File | What it holds |
|---|---|
| `eval/bin.ts` | Entry point; `run.ts` holds everything it calls, so the runner is testable. |
| `eval/run.ts` | Argument parsing, the two experiment definitions, the graders that assemble scores. |
| `eval/datasets.ts` | The cases, and the zod schemas each item's input is parsed through. |
| `eval/scorers.ts` | `parseDiff` and one function per score. Pure — no Langfuse, no model. |
| `eval/tasks.ts` | Runs a graph over one case and returns its body, findings, and structured output. |
| `eval/github.ts` | `StaticGitHubClient` — one case as a `GitHubClient`. |
| `eval/llm.ts` | `RecordingLlmClient` — an `LlmClient` that keeps every structured reply. |
| `eval/langfuse.ts` | The OpenTelemetry provider, span processor, and client, and the local-stack credential fallback. |
| `eval/docker-compose.yml` | The local Langfuse stack `npm run eval:up` starts. |

The datasets live in the repository rather than in Langfuse: a case is reviewed in a pull
request like any other code, and a run needs no network to be reproducible. Pushing them up
as a Langfuse dataset — so runs link to dataset items and compare across versions — is a
later step, and the schemas in `datasets.ts` are what will parse them on the way back down.
