# Install

## Requirements

- Node.js 22 or newer
- npm
- An [NVIDIA API key](https://build.nvidia.com) for model calls
- A GitHub App (only for `pr_review` / `issue_review` — see [`USAGE.md`](USAGE.md#the-github-app))

## From source

```bash
git clone https://github.com/kaiquekandykoga/angel.git
cd angel
npm install
cp .env.example .env     # fill in the variables — see USAGE.md#configuration
```

Run directly from TypeScript sources via [`tsx`](https://tsx.is), no build step:

```bash
npm run angel chat
```

Or compile and run the built output:

```bash
npm run build
node dist/bin.js chat
```

## As a global command

Compile, then link the package so the `angel` bin is on your `PATH`:

```bash
npm run build
npm link
angel chat
```

`npm unlink -g angel` removes it.

## Verify

```bash
npm run ci    # biome ci → tsc --noEmit → vitest run
```

All three should pass clean on an unmodified checkout.

## Next steps

- [`USAGE.md`](USAGE.md) — commands, options, environment variables, the GitHub App
- [`TESTING.md`](TESTING.md) — running and adding to the test suites
