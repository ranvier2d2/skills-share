# Targeting & pruning heuristics

## Where to place instruction files

Prioritize directories that represent a **decision boundary** for an agent:

- Language/package boundaries (`src/`, `app/`, `packages/*`, `services/*`, `libs/*`)
- Execution surfaces (`scripts/`, `bin/`, `cli/`)
- Quality gates (`tests/`, `e2e/`, `docs/`, CI/config directories)
- Risky areas (auth, payments, infra, migrations)

Default: write a root file + a handful of subdir files. Add more only when they reduce repeated mistakes.

## Where *not* to place instruction files

Never generate instruction files in:

- Vendored deps (`node_modules/`, `.venv/`, `vendor/`)
- Caches (`__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`)
- Build outputs (`dist/`, `build/`, `.next/`, `.turbo/`)
- Large auto-generated trees (protobuf outputs, compiled assets), unless the user explicitly asks.

## How to keep files effective

- **Scream early:** the first lines should answer “what is this folder?”
- **Commands > advice:** give exact commands for the local fast check.
- **Layer, don’t copy:** root = global; subdir = deltas/overrides.
- **Keep it small:** the total discovered instruction chain has a size cap (32 KiB by default). Split by adding nested files if needed.

