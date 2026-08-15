---
name: make-plan
description: >
  Turn an instruction into an implementation plan, hand the tasks off to the appropriate agents, then commit and push. Use when the user says "make plan", "plan this", or asks for a plan to be built and carried out
model: opus
effort: high
---

# Make plan
Plan the requested work, delegate each task to the right agent, then ship it

The instruction to plan is whatever the user passed to this skill (or their preceding message).

## Steps
1. Scope: restate the request in one line. Read only the lines needed to plan it (`Grep`, specific line ranges — never whole trees). Spawn `Explore` only when the relevant code cannot be located in two or three targeted searches.
2. Plan: write a numbered, ordered task list. Each task states the behavior, the files it touches, and how it is verified. Delegate to the `Plan` agent only for genuine architectural trade-offs.
3. Confirm: show the plan and get approval before any code changes. Use `AskUserQuestion` only when a real ambiguity would change the plan.
4. Delegate: one task per agent invocation, each carrying its files and acceptance criteria so the agent needs no discovery of its own.
   - Ruby behavior → `ruby-engineer`
   - Rust behavior (`lib/tui`) → `rust-engineer`
   - Anything else → `claude`
   A Ruby change to the `rake a:status:json` or `rake tui:catalog` payloads is also a Rust task: bump `backend::model::CONTRACT_VERSION` and regenerate `lib/tui/tests/fixtures/{status,catalog}.json`.
   Run independent tasks in parallel; run dependent tasks in order, passing the previous result forward. Do the work inline when it is smaller than the handoff.
5. Ship: take each agent's report at face value — they run their own suites — and run `/commit-and-push-changes`.
6. Minimal report: tasks completed, suite results as reported by the agents, PR URL.
