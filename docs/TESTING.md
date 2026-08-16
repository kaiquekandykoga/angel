# Testing

`uv run ci` runs the whole suite — see [`USAGE.md`](USAGE.md) for the commands. The tests
are split in two:

| Tree | What lives there | How it stubs the world |
|---|---|---|
| `tests/unit_tests/` | Graphs, nodes, the REPL, logging, the CLI — everything driven through a fake. | `FakeGitHubClient` / `FakeClient` from `tests/conftest.py`. No HTTP at all. |
| `tests/integration_tests/` | `HttpGitHubClient` and `InstallationTokenProvider` — the code that actually speaks HTTP. | [`respx`](https://lundberg.github.io/respx/) routes serving recorded GitHub payloads from `tests/fixtures/`. Still no network. |

```bash
uv run pytest -m "not integration"   # fakes only, fastest
uv run pytest -m integration         # client code over recorded payloads
```

Everything under `tests/integration_tests/` is marked `integration` automatically by that
tree's `conftest.py` — you do not mark tests by hand.

**Why both.** `FakeGitHubClient` encodes the same assumptions as the real client, so it can
never falsify them; that is exactly how the missing pagination went unnoticed. The recorded
fixtures are full-shape GitHub responses (every field the API really returns, sanitized),
so a test can serve a `Link: rel="next"` header and prove that page 2 is dropped.

**Adding a fixture.** Drop the sanitized JSON (or raw text, for diffs) under
`tests/fixtures/github/` and load it with the `load_fixture` fixture:

```python
def test_something(load_fixture):
    payload = load_fixture("github/pulls_page1.json")
```

Keep the whole response shape rather than the handful of fields the client reads today —
the extra fields are what makes the fixture useful when the client grows. Never commit a
real token: the recorded installation token is a redacted placeholder.

Some integration tests are `xfail(strict=True)` and name an open item in [`TODO.md`](TODO.md).
That is deliberate — they document a known bug against real payloads. When the fix lands,
the test starts passing and the marker gets deleted in the same PR.
