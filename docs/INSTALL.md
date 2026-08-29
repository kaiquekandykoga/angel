# Install

## Requirements

- Node.js 22+, npm
- [NVIDIA API key](https://build.nvidia.com) for model calls
- GitHub App — only for `pr_review`/`issue_review`, see [`USAGE.md`](USAGE.md#the-github-app)
- Docker with Compose v2 — only for `npm run eval`, which reports to a local Langfuse, see [`EVAL.md`](EVAL.md#the-local-langfuse)

## From source

```bash
git clone https://github.com/kaiquekandykoga/angel.git
cd angel
npm install
cp .env.example .env
```

Run via [`tsx`](https://tsx.is) (no build):

```bash
npm run angel chat
```

Or build + run:

```bash
npm run build
node dist/apps/cli/bin.js chat
```

## As a global command

```bash
npm run build
npm link
angel chat
```

`npm unlink -g angel` to remove.

## Verify

```bash
npm run ci    # biome ci → tsc --noEmit → vitest run
```
