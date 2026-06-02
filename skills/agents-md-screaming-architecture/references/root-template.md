# Root instructions template (Screaming Architecture)

Use this as a starting point for a repo-root `AGENTS.md` (or `.agents.md` when configured/asked).

## What this repo is

- [One sentence] This repo is for: …
- [Optional] Primary entrypoints: …

## Repository expectations

- Keep changes minimal and scoped to the request.
- Prefer fixing root causes over surface patches.
- If you change public behavior, update docs and tests.

## Setup

- Runtime / version: …
- Install deps: `…`
- Run app/CLI: `…`

## Fast checks (must-run)

- Tests: `…`
- Lint/format/typecheck (if applicable): `…`

## Architecture map

- `src/` / `app/` / `packages/` / `services/`: [what they are for]
- `scripts/`: [one-off tools, safe to run from root]
- `tests/`: [test strategy, how to run]
- `docs/`: [docs conventions]

## Guardrails

- Dependencies: [when to add prod deps, lockfile rules]
- Secrets: [where they live, how to load locally]
- Generated output: [where it goes; do not commit unless asked]

