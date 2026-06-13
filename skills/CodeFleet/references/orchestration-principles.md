# Orchestration Principles

Use this reference when deciding how the orchestrator decomposes, sequences,
branches, and supervises fleet work.

## Worktree Isolation

Every worker gets its own git worktree and branch. Worktrees prevent local
checkout and index collisions, but they do not solve semantic dependencies.
The dependency graph decides what can run in parallel.

```bash
git worktree add ../$(basename "$PWD")-fleet-<run-id>-task-1 -b fleet/<run-id>/task/1-<slug>
git worktree list
git worktree remove ../$(basename "$PWD")-fleet-<run-id>-task-1
git branch -d fleet/<run-id>/task/1-<slug>
```

- One branch per task: `fleet/<run-id>/task/<n>-<slug>`.
- Workers commit frequently inside their worktree.
- Never let two workers share a worktree or branch.

## DAG-Based Parallelism

Before spawning workers, run `Workflows/DependencyGraph.md`. The orchestrator
must classify every edge:

- `blocking`: downstream task waits for a reviewed checkpoint bundle.
- `soft`: tasks may run in the same wave, but the edge creates a seam
  obligation for wave integration and final merge.

Always pause and show the user the wave table and edge rationale before
execution. After approval, continue autonomously unless a material contract
change, new blocker, task split, or risk increase invalidates the graph.

## Ambiguity Handling

Do not block a fleet on routine questions. If a worker or orchestrator hits an
ambiguity, spawn a sub-agent to investigate the codebase, find precedent, and
recommend a best-fit tradeoff. Escalate to the user only when investigation
cannot resolve a material decision.

```text
Ambiguity -> Agent(general-purpose):
  "Search the codebase for how X is handled. Report the established convention
   and the best-fit choice for <decision>."
```

Adopt the answer, document the assumption, and continue.

## Task Sizing

Scope each task to a meaningful 1-2 hour unit of work. Smaller tasks waste
spawn and coordination overhead. Larger tasks bloat context and make review or
merge failures harder to diagnose. If a task looks larger than 2 hours, split
it before spawning.

## Thought-Level Calibration

Do not blanket-max every worker. Before spawning, an assessor sub-agent reads
the task spec and key referenced files, scores the task, and recommends a level
from L1 to L4. The orchestrator may override, but it must record why.

Axes are scored 0/1/2:

- A: spec clarity, inverted. Clearer specs score lower.
- B: implementation complexity.
- C: shared or blast surface.
- D: verification surface.
- E: precedent, inverted. Clear in-repo patterns score lower.

| Level | Sum | Worker effort | ultrathink | Review panel | Re-review cap | Verify |
| --- | --- | --- | --- | --- | --- | --- |
| L1 Mechanical | 0-2 | medium | no | 1 lens, usually C | 1 | read committed diff/output only |
| L2 Standard | 3-5 | high | yes | 3 lenses, C+CM+P | 2 | diff/output + 1 browser snapshot |
| L3 Demanding | 6-7 | high | yes | 5 lenses, +E+S | 3 | full browser flow |
| L4 Critical | 8-10 | max | yes | 8 lenses + ACJ | 3 | full browser + arbiter pass |

L4 should usually feed back into decomposition rather than simply receiving
more effort. Model choice is not calibrated here; all workers use the session
default model.

## Division Of Labor (Claude-only, two layers)

This is a **Claude-only** orchestrator — there is no Codex. Labor splits by
**layer**, not by model (ADR 0002 / 0003):

- **The skill (the agent, between waves)** owns governance: decompose → DAG →
  thought-level calibration → **user approval** → for each wave, call the Workflow
  tool → write the ledger → `git merge` the wave (one branch at a time) → seam
  checks → FinalMerge → `/review`. The skill touches the filesystem, git, and the
  clock; it pauses for approval/integration gates that a Workflow cannot express.
- **The wave Workflow (`workflow-scripts/wave-runner.js`, inside a wave)** owns the
  fan-out: `pipeline(work → review → fix → verify)`, one item per ready-set task,
  with `isolation: "worktree"` per worker. It returns pure structured data and
  touches no files.

**Review independence without a second model.** The adversarial review panel is
parallel Claude subagents, each carrying **one distinct skeptical lens** and told
to *refute* the work; corroboration across lenses (multi-lens findings rank higher)
recovers most of what a separate reviewer model would have bought. Verification is a
**separate** Claude subagent that independently reproduces evidence — worker-says-
done is never enough.

**Subagents are not commands.** A worker/reviewer/verifier only runs because a
stage brief in `wave-runner.js` spawns it; the rescue pass is a single higher-effort
Claude subagent at the re-review cap (no external rescue engine).
