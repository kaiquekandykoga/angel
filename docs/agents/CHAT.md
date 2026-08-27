# `chat`

An interactive assistant REPL over a one-node graph, in `apps/server/agents/chat/`.
`apps/cli/repl.ts` reads a line at a time and stops at `/exit` or Ctrl-D; the `ChatSession`
in `agents/chat/session.ts` holds the `threadId` generated at session start and invokes the
graph once per line. The conversation grows via LangGraph's `MessagesAnnotation`
(`addMessages` reducer), and the compiled graph carries a checkpointer (`MemorySaver` by
default), so each invocation appends to the same thread — history lives only in memory, gone
when the process ends.

```
  START
    |
    v
  +----------+
  | call_llm |  <--- NVIDIA model: system prompt + conversation so far
  +----------+
    |  reply appended to state.messages
    v
   END
```

| Node | Does |
|---|---|
| `call_llm` | Prepends the system prompt to the accumulated messages, calls the model, returns the reply for the reducer to append |

Unlike the review agents, `chat` returns an unvalidated `string` — no schema, no structured
output. `--dry-run` is rejected for this command; see [`USAGE.md`](../USAGE.md#chat).
