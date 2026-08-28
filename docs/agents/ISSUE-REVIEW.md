# `issue_review`

Same shape as [`pr_review`](PR-REVIEW.md), over the open issues of the same discovered
repositories, in `apps/server/agents/issue-review/`. Only issues labeled `angel` count; the
label is created on each repository if missing. Review-selection logic (never commented, or
`updatedAt` newer than the last comment) is in [`USAGE.md`](../USAGE.md#issue_review).

```
  START
    |
    v
  +--------------+
  | fetch_issues |  <--- GitHub: installation repositories,
  +--------------+       ensures the `angel` label exists,
    |                    then their open issues labeled `angel` + comments
    |  IssueContext ({ target, comments }), only the ones due for review
    v
  +---------------+
  | review_issues |  <--- NVIDIA model: an IssueReviewOutput
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
| `fetch_issues` | Ensures each repository has the `angel` label, lists issues carrying it and their comments, keeps the ones due for review, and emits an `IssueContext` (the issue plus its comments) |
| `review_issues` | Asks the model for an `IssueReviewOutput` (summary, findings, acceptance criteria, suggested approach) given the title, description, and existing comments, then renders it to the comment body |
| `post_review_comments` | Shared with `pr_review` — posts each review as an issue comment |

`--dry-run` applies here too, by the same wrapper.

How failures are isolated and retried is in [`README.md`](README.md#failure-isolation-and-retries).
