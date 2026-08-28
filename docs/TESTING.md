# Testing

`npm run ci` runs the whole gate — `biome ci`, then `tsc --noEmit`, then `vitest run`.

```bash
npm run test:unit          # fakes only, fastest
npm run test:integration   # client code over recorded payloads
npm run coverage           # the same tests, with a coverage report
```

`tests/` mirrors the repository root — `tests/apps/` (`cli/` and `server/`),
`tests/packages/` (`shared/`), `tests/eval/` (the harness: scorers, datasets, and the tasks
that drive a graph; never calls a model or Langfuse). Inside those trees the *kind* of test
is in the filename, not the path, so `client.test.ts` and `client.integration.test.ts` sit
next to each other and next to the `client.ts` they cover:

| Suite | What it covers | How it stubs the world |
|---|---|---|
| `*.test.ts` | Everything driven through a fake. | `FakeGitHubClient` / `FakeLlmClient` from `tests/helpers/`. No HTTP at all. |
| `*.integration.test.ts` | `HttpGitHubClient` and `InstallationTokenProvider` — the code that actually speaks HTTP. | `FakeFetch` from `tests/helpers/fetch.ts`, serving recorded GitHub payloads from `tests/fixtures/`. Still no network. |

`tests/eval/` runs with the unit suite: the scorers are pure functions, and
`tests/eval/tasks.test.ts` drives the real review graphs through `FakeLlmClient`, so the
whole eval path is exercised without spending a token. The paid, non-deterministic half is
`npm run eval` — see [`EVAL.md`](EVAL.md).

**Why both.** `FakeGitHubClient` encodes the same assumptions as the real client, so it can
never falsify them; that's exactly how the missing pagination went unnoticed. The recorded
fixtures are full-shape GitHub responses (every field the API really returns, sanitized), so
a test can serve a `Link: rel="next"` header and prove page 2 isn't dropped.

## The helpers

Everything shared between suites lives in `tests/helpers/`, imported explicitly — no
implicit fixture injection:

| Helper | Gives you |
|---|---|
| `fetch.ts` | `FakeFetch` — routes `METHOD /path` to a `Response`, records every call |
| `fixtures.ts` | `loadFixture(name)` — reads `tests/fixtures/<name>`, parsing `.json` |
| `github.ts` | `FakeGitHubClient` — an in-memory GitHub holding whatever the test sets up |
| `llm.ts` | `FakeLlmClient` — scripted replies, and `failStructuredCall` to fail the nth call |
| `logs.ts` | `useLogCapture()` — installs a capturing log handler for the surrounding tests; `readJsonLines(path)` reads a written log back |
| `model.ts` | `aiMessage()` and `FakeChatModel` — replies carrying the metadata `NvidiaClient` reads |
| `stream.ts` | `MemoryStream` — an `OutputStream` recording what was written, with a tty flag |
| `keys.ts` | `rsaKeyPair()` — an RSA key pair, generated once per test process |
| `tmp.ts` | `useTemporaryDirectory()` — a fresh temp directory per test, `chdir`'d into and removed after |
| `ansi.ts` | `stripAnsi(text)` — compare styled output as plain text |

**Adding a fixture.** Drop the sanitized JSON (or raw text, for diffs) under
`tests/fixtures/github/` and load it with `loadFixture("github/pulls_page1.json")`.
`tests/fixtures/injection/` holds the prompt-injection material instead — a PR body carrying
a forged fence, a forged sha marker, and a payout link, plus the review output a model that
obeyed it would return. Both review agents' node suites drive them through
`finalizeReviewBody()` and assert nothing policy-violating survives; `github/mixed.diff`
covers the diff filter's lockfile, `dist/`, binary, and minified cases. Keep the
whole response shape rather than the handful of fields the client reads today — the extra
fields are what makes the fixture useful when the client grows. Never commit a real token:
the recorded installation token is a redacted placeholder.

## In CI

`.github/workflows/ci.yml` runs the same three checks on every push and pull request: lint
and typecheck and build once on Linux, then the test suite across a matrix of Linux and
macOS on Node 22 and 24 — four jobs, none of which fail fast. Nothing there needs a secret,
since neither suite touches the network.

`.github/dependabot.yml` keeps the inputs to those jobs current: weekly npm and GitHub
Actions checks, with updates grouped (`@langchain/*`, dev dependencies, production
minor/patch, all actions) so a week's bumps arrive as a few pull requests instead of a dozen.
Each one runs the full matrix above, so CI is what says whether a bump is safe.
