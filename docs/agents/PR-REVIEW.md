# `pr_review`

Reviews open pull requests across every repository the App installation can reach —
discovered at run time, in `apps/server/agents/pr-review/`. Only PRs labeled `angel` count;
the label is created on each repository if missing. Review-selection logic (never commented,
or head sha changed since the last `<!-- angel: sha=… -->` marker) is in
[`USAGE.md`](../USAGE.md#pr_review).

```
  START
    |
    v
  +---------------------+
  | fetch_pull_requests |  <--- GitHub: installation repositories,
  +---------------------+       ensures the `angel` label exists,
    |                           then their open PRs labeled `angel` + comments
    |  PullRequestContext ({ target, comments }), only the ones due for review
    v
  +----------------------+
  | review_pull_requests |  <--- GitHub: the PR diff
  +----------------------+  <--- NVIDIA model, once per lens (security, quality,
    |                             performance): a PullRequestReviewOutput each
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
| `fetch_pull_requests` | Ensures each repository has the `angel` label, lists PRs carrying it and their comments, keeps the ones due for review, and emits a `PullRequestContext` (the PR plus its comments) |
| `review_pull_requests` | Fetches the diff, then asks the model for a `PullRequestReviewOutput` (summary + severity-tagged findings) three times over the same title, description, existing comments, and diff — once per specialised lens (security, quality, performance), each prompted to stay in its lane — and merges the three into one comment body with a finding section per lens. A lens that fails fails the whole pull request: nothing is posted and it is retried next run |
| `post_review_comments` | Posts each review as an issue comment on its PR |

Under `--dry-run` the wiring is identical — the flag wraps the GitHub client in a read-only
`dryRunClient`, so the label check in `fetch_pull_requests` and the comment in
`post_review_comments` become logged no-ops while reads behave as usual. See
[`USAGE.md`](../USAGE.md).

How failures are isolated and retried is in [`README.md`](README.md#failure-isolation-and-retries).
