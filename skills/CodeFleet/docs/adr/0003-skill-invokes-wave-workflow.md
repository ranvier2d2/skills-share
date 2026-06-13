# 0003 — Verified-live runtime mechanics: skill→workflow invocation, script shape, and isolation

Accepted. Supersedes the `await runWorkflow("wave-runner.js", payload)` fiction **and** the `workspace:{mode}` isolation option (ADR 0002 C5/C6) in earlier drafts of `SKILL.md` / `Workflows/RunTaskFleet.md` / `references/review-verification.md`. Every decision here was confirmed by **executing the real artifacts** (an API probe, a runtime-faithful dry-run harness, a live seam probe, and a full live wave that ran the actual `wave-runner.js` end-to-end).

## Context

The hybrid splits responsibilities across two layers (ADR 0002): the **skill** governs (DAG → approval → per-wave run → integration → seam gate), and a **native Workflow** executes each wave. That left one mechanism unverified: *how does a skill — which is markdown the agent follows, not a running program — actually invoke a workflow script, once per wave, passing that wave's payload and reading the result?*

Authoritative answers (Claude Code docs, v2.1.160+, confirmed 2026-06-03):

- A skill has **no code runtime and no `runWorkflow()` primitive.** The only mechanism is: the agent, following the skill's instructions, **calls the Workflow tool.** The per-wave "loop" is therefore the **agent driving it turn by turn** (call Workflow → read structured result → write ledger → git-integrate → next wave), with approval/integration gates living **between** Workflow calls in the agent's turn logic — never inside a script (a Workflow runs to completion with no mid-run input).
- The Workflow tool passes input to a script as a **global named `args`** and **executes the script body** (top-level `await` runs). It does **not** call an exported function for you. The public docs show no script-path parameter (saved workflows are invoked as `/name` after a manual UI save); the agent's Workflow tool contract *does* accept `{scriptPath, args}` (and `{scriptPath, resumeFromRunId}` for resume), which is what we rely on.

## Decision

1. **Invocation.** The agent runs each wave with `Workflow({ scriptPath: "<skill-dir>/workflow-scripts/wave-runner.js", args: wavePayload })`. **Fallback** (if `scriptPath` is unavailable in some context): the skill instructs the agent to read the file and pass its body as the inline `script` string with the same `args`. Either way the on-disk file is the single source of truth; neither path requires a manual `/workflows → s` save.

2. **Script shape: self-executing, `args`-driven.** `wave-runner.js` is an *executable workflow body*, not an importable module. It defines `async function runWave(wave)` and `async function describe()` (plain functions, **not** `export default`), and ends with a top-level tail that reads the ambient `args` and dispatches:
   ```js
   // runtime set globalThis.args and is executing this body
   return (args && args.describe) ? describe() : await runWave(args);
   ```
   `args` **is** the wave payload. `args.describe:true` returns the self-description; `args.dry_run:true` (read inside `runWave`) walks the plan with stubbed agents.

3. **Self-description is runtime-reachable.** `describe()` is reachable via `args.describe:true` so the skill can introspect the input/output contract before the first wave, not only by reading source. (A bare run with no `args` also returns `describe()`, so an accidental empty invocation is harmless.)

4. **Isolation (supersedes ADR 0002 C5/C6).** A live wave proved `agent(…, {workspace:{mode}})` is **inert** — the runtime accepts but discards unknown agent options, so no worktree was created and no ref checked out (the probe agents only succeeded by doing the git themselves). The verified mechanism:
   - **Write stages (work, fix, rescue):** pass the real workflow-level flag `agent(…, { isolation: "worktree" })`. The runtime creates a fresh worktree on an **engine-auto-named** branch; the brief then `git checkout -b fleet/<run-id>/task/<N>-<slug>` (worker) or `git checkout <that branch>` (fix/rescue) and commits there — the named branch is what integration merges.
   - **Read stages (review, verify):** **no** isolation flag (a second `isolation:"worktree"` would be a different empty tree). The brief reads the committed branch tip from the shared git object store (`git diff <base>...<branch>`, `git show <branch>:<file>`, or a scratch `git worktree add`).
   - **Fix subagents run sequentially**, not in parallel — git forbids checking out one branch in two worktrees at once, so each ACCEPT fix commits before the next starts (tasks across the wave still pipeline).
   - Isolation worktrees **persist** once they hold a commit; the **skill** removes them at integration/teardown.
   This was confirmed by a full live wave: `wave-runner.js` ran end-to-end, created `fleet/<run-id>/task/N-<slug>`, committed, and an independent verifier checked out the SHA and ran `mix test` (273 passed).

## Consequences

- The skill's invocation prose is **agent-calls-the-Workflow-tool**, not a `runWorkflow()` call. `SKILL.md` and `RunTaskFleet.md` are corrected to match.
- The script is verified by a harness that sets `globalThis.args` and **executes the body** (faithful to the runtime), not by hand-calling `runWave(...)` — the latter masked the export-never-invoked gap.
- State between waves lives where the agent can reach it across turns: the `.orchestrator/fleet.json` ledger (and git), plus the agent's own context. Optional ergonomics confirmed available but not required: `` !`…` `` in SKILL.md can pre-embed the live ledger/current wave as context; a `PreToolUse` hook on the Workflow tool can hard-gate a wave; `SessionStart` hooks can re-inject context after compaction.

## Alternatives rejected

- **Keep `export default` + a thin importing wrapper.** Workflow scripts cannot `import` arbitrary files, so this collapses into "inline the whole script every time" — i.e. always-inline, which discards `scriptPath` and the file-as-source-of-truth benefit.
- **Save as a `/command` and invoke per wave.** Saving is a manual UI step and a slash-command is awkward to call programmatically with a fresh payload each wave; it does not fit an agent-driven loop.
