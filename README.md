# Nishikihebi

The idea is to build a Multi-Agent System using Python reflected by [kirinn](https://github.com/kaiquekandykoga/kirinn)

## Run app

Copy `.env.example` to `.env` and fill in your `NVIDIA_API_KEY`. The app loads `.env` automatically; an already-exported shell variable still takes precedence. `GITHUB_TOKEN` is only required for `pr_review`.

```bash
uv sync
uv run nishikihebi chat
uv run nishikihebi pr_review
```
