# Nishikihebi

The idea is to build a Multi-Agent System using Python reflected by [kirinn](https://github.com/kaiquekandykoga/kirinn)

## Run app

Copy `.env.example` to `.env` and fill in the variables below.

| Variable | Command | Required | Description |
|---|---|---|---|
| `NISHIKIHEBI_NVIDIA_API_KEY` | `chat`, `pr_review` | Yes | NVIDIA API key from https://build.nvidia.com — used for all model calls. |
| `NISHIKIHEBI_GITHUB_TOKEN` | `pr_review` | Yes for `pr_review` | GitHub token with permission to read pull requests and write issue comments on the target repository. |

The app loads `.env` automatically; an already-exported shell variable still takes precedence.

```bash
uv sync
uv run nishikihebi chat
uv run nishikihebi pr_review
```
