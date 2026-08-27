# Testing

`npm run ci` runs the whole gate — `biome ci`, then `tsc --noEmit`, then `vitest run`. See
[`USAGE.md`](USAGE.md) for the commands. Tests split in two:

| Tree | What lives there | How it stubs the world |
|---|---|---|
| `tests/unit/` | Graphs, nodes, the REPL, logging, the CLI — everything driven through a fake. | `FakeGitHubClient` / `FakeLlmClient` from `tests/helpers/`. No HTTP at all. |
| `tests/integration/` | `HttpGitHubClient` and `InstallationTokenProvider` — the code that actually speaks HTTP. | `FakeFetch` from `tests/helpers/fetch.ts`, serving recorded GitHub payloads from `tests/fixtures/`. Still no network. |

```bash
npm run test:unit          # fakes only, fastest
npm run test:integration   # client code over recorded payloads
npm run coverage           # the same tests, with a coverage report
```

Split is by directory — nothing to mark by hand.

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
`tests/fixtures/github/` and load it with `loadFixture`:

```ts
const payload = loadFixture("github/pulls_page1.json");
```

Keep the whole response shape rather than the handful of fields the client reads today — the
extra fields are what makes the fixture useful when the client grows. Never commit a real
token: the recorded installation token is a redacted placeholder.

## In CI

`.github/workflows/ci.yml` runs the same three checks on every push and pull request: lint
and typecheck and build once on Linux, then the test suite across a matrix of Linux and
macOS on Node 22 and 24 — four jobs, none of which fail fast. Nothing there needs a secret,
since neither suite touches the network.
</content>
