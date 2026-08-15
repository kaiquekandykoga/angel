# Graphs

Each command is a [LangGraph](https://langchain-ai.github.io/langgraph/) state graph, and
each one owns a directory under `src/nishikihebi/agents/` — `agents/chat/`,
`agents/pr_review/`, `agents/issue_review/`. Inside each, `graph.py` wires the nodes,
`state.py` declares the state threaded between them, `prompts.py` holds the system prompt,
and `nodes.py` holds the nodes themselves: factories that take their dependencies (LLM
client, GitHub client) and return the node function, so a graph can be built against fakes
in tests. Anything two agents share — the `Review` record, the `post_review_comments` node,
the comment helpers — lives in `agents/_shared.py`. Those dependencies sit behind
`Protocol` seams in `src/nishikihebi/clients/`, and the reviewer login, label, and label
colour in `src/nishikihebi/settings.py`.

## `chat`

An interactive assistant REPL over a one-node graph. `agents/chat/repl.py` reads a line at
a time and stops at `/exit` or end of input (Ctrl-D), and holds the `thread_id`
generated when the session starts, invoking the graph once per line. The conversation
grows because `ChatState.messages` uses the `add_messages` reducer and the compiled graph
carries a checkpointer (`MemorySaver` by default), so each invocation appends to that same
thread — and the history lives only in memory, so it ends with the process.

```
  START
    |
    v
  +----------+
  | call_llm |  <--- NVIDIA model: system prompt + conversation so far
  +----------+
    |  reply appended to state["messages"]
    v
   END
```

`call_llm` prepends the system prompt to the accumulated messages, calls the model, and
returns the reply for the reducer to append.

## `pr_review`

Reviews open pull requests across every repository the App installation can reach — the
set is discovered at run time from GitHub, so granting or revoking the App's access to a
repository is all it takes to add or drop it. Only PRs labeled `nishikihebi` are
considered; the label is created on each repository if it doesn't already exist. A
labeled pull request is picked up when `kandy-nishikihebi[bot]` has never commented on
it, or when its head commit is newer than that last comment — so a PR is re-reviewed only
after new commits land.

```
  START
    |
    v
  +---------------------+
  | fetch_pull_requests |  <--- GitHub: installation repositories,
  +---------------------+       ensures the `nishikihebi` label exists,
    |                           then their open PRs labeled `nishikihebi` + comments
    |  PullRequestContext (pull request + comments), only the ones due for review
    v
  +----------------------+
  | review_pull_requests |  <--- GitHub: the PR diff
  +----------------------+  <--- NVIDIA model: one review comment
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
| `fetch_pull_requests` | Ensures each repository has the `nishikihebi` label, lists PRs carrying it and their comments, keeps the ones due for review, and emits `PullRequestContext` (the PR plus its comments) |
| `review_pull_requests` | Fetches the diff and asks the model for one review comment, given the title, description, existing comments, and diff |
| `post_review_comments` | Posts each review as an issue comment on its PR |

## `issue_review`

Same shape as `pr_review`, over the open issues of the same discovered repositories. Only
issues labeled `nishikihebi` are considered; the label is created on each repository if
it doesn't already exist. A labeled issue is picked up when `kandy-nishikihebi[bot]` has
never commented on it, or when the issue's `updated_at` is newer than that last comment —
which covers both an edited description and new comments.

```
  START
    |
    v
  +--------------+
  | fetch_issues |  <--- GitHub: installation repositories,
  +--------------+       ensures the `nishikihebi` label exists,
    |                    then their open issues labeled `nishikihebi` + comments
    |  IssueContext (issue + comments), only the ones due for review
    v
  +---------------+
  | review_issues |  <--- NVIDIA model: one review comment
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
| `fetch_issues` | Ensures each repository has the `nishikihebi` label, lists issues carrying it and their comments, keeps the ones due for review, and emits `IssueContext` (the issue plus its comments) |
| `review_issues` | Asks the model for one review comment, given the title, description, and existing comments |
| `post_review_comments` | Shared with `pr_review` — posts each review as an issue comment |

## Known gaps

The three graphs are linear and sequential, and [`TODO.md`](TODO.md) §6 lists what that
leaves on the table: no `Send` fan-out, so ten PRs mean ten serial model calls with no
per-item failure isolation (§6.2, §4.2); no checkpointer on the review graphs, so a crash
mid-run loses everything (§6.1); no structured output, so a review body is an unvalidated
`str` (§6.3); and no streaming in the chat REPL (§6.6).
