# Codex Exec Reference (Research Notes)

This reference is based on local CLI help output captured from:
- `codex exec --help`
- `codex exec resume --help`
- `codex exec review --help`

## `codex exec` essentials
- Purpose: run Codex non-interactively for a focused task.
- Prompt input: direct argument or stdin.
- Working root: `-C, --cd <DIR>`.
- Sandbox: `-s, --sandbox read-only|workspace-write|danger-full-access`.
- Model: `-m, --model <MODEL>`.
- Profile: `-p, --profile <CONFIG_PROFILE>`.
- Output capture: `-o, --output-last-message <FILE>`.
- Event stream: `--json` (JSONL to stdout).
- Safety escape hatch: `--dangerously-bypass-approvals-and-sandbox` (avoid by default).

## `codex exec resume` essentials
- Purpose: continue a prior session by id/name, or use `--last`.
- Prompt-on-resume supported.
- Supports `--json`, `-m`, feature flags, and dangerous bypass flag.

## `codex exec review` essentials
- Purpose: review code changes in repo context.
- Diff selectors:
  - `--uncommitted`
  - `--base <BRANCH>`
  - `--commit <SHA>`
- Supports custom prompt and `--json` output.

## Practical subagent pattern
1. Delegate narrow task with `codex exec`.
2. Capture final message to file with `-o`.
3. Optionally capture JSONL events with `--json`.
4. Parent process reads artifacts and decides next actions.
