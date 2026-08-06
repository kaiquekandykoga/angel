# Nishikihebi

The idea is to build a Multi-Agent System using Python reflected by [kirinn](https://github.com/kaiquekandykoga/kirinn)

## Run app

Copy `.env.example` to `.env` and fill in the variables below.

| Variable | Command | Required | Description |
|---|---|---|---|
| `NISHIKIHEBI_NVIDIA_API_KEY` | `chat`, `pr_review` | Yes | NVIDIA API key from https://build.nvidia.com — used for all model calls. |
| `NISHIKIHEBI_GITHUB_APP_ID` | `pr_review` | Yes for `pr_review` | ID of the GitHub App used to authenticate; needs read access to pull requests and write access to issue comments on the target repositories, and must be installed on them. |
| `NISHIKIHEBI_GITHUB_PRIVATE_KEY_PATH` | `pr_review` | Yes for `pr_review` | Path to the GitHub App's private key (`.pem`). |

The app loads `.env` automatically; an already-exported shell variable still takes precedence.

```bash
uv sync
uv run nishikihebi chat
uv run nishikihebi pr_review
```

## Development

Run `uv run ci` to lint, type-check, and test locally — this is the CI signal for this repo.
