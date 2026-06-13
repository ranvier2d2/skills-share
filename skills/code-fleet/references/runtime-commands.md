# Runtime Commands (hybrid)

The hybrid orchestrator uses **native Workflows** for per-wave execution and
**plain git** for integration. There is **no cmux and no Codex** — if you see
cmux/Codex commands anywhere, they are from the pre-hybrid skill and do not apply.
Load this when actually driving a run.

## Invoking a wave (the agent calls the Workflow tool)

A skill is markdown the agent follows; it has no `runWorkflow()` primitive. The
agent runs each approved wave by calling the **Workflow tool** once with the wave
script and the wave payload (ADR 0003):

```text
Workflow({ scriptPath: "<this-skill-dir>/workflow-scripts/wave-runner.js", args: <wavePayload> })
```

- `args` becomes the script's `args` global; the script self-executes and returns
  the 1c wave-result.
- **Fallback** if `scriptPath` is unavailable in some context: read
  `workflow-scripts/wave-runner.js`, strip the `export` keyword from `meta`, and
  pass the body as the inline `script` string with the same `args`.
- **Introspect the contract** before the first wave:
  `Workflow({ scriptPath: …, args: { describe: true } })` returns the input/output
  schema. A bare run (no `args`) also returns `describe()`.
- **Dry-run** (no model calls, no worktrees, no mix — walks the plan):
  include `dry_run: true` in the wave payload.

The wave script owns everything *inside* a wave (work → review → fix → verify,
worktree isolation, the lens panel, the concurrency semaphore). The agent owns
everything *between* waves (below).

## Git worktrees (isolation + teardown)

Write stages inside the wave use the runtime's real `isolation: "worktree"` flag;
the worker brief checks out the named branch. The **skill** owns teardown, because
engine worktrees **persist once they hold a commit**:

```bash
git worktree list                                  # see engine-created fleet worktrees
git worktree remove --force <path>                 # per leftover worktree, after integration
git worktree prune
git branch -D fleet/<run-id>/task/<N>-<slug>        # after the work is captured
```

`deps/`, `_build/`, and `mix.lock` are gitignored — workers leave them unstaged so
merges stay clean.

## Wave integration (plain git, one branch at a time)

After a wave Workflow returns, the agent integrates it:

```bash
# branch the wave integration off the base (wave 1) or the previous wave integration (wave k>1)
git checkout -B integration/<run-id>/wave-<k> <base-or-previous-wave-integration>

# merge each task branch from the wave — ONE AT A TIME, never an octopus merge
git merge --no-ff fleet/<run-id>/task/<N>-<slug> -m "integrate(wave-<k>): <slug> (task N) — checkpoint <sha>"

# verify the integrated tree is green before unblocking dependents
mix deps.get && mix compile --warnings-as-errors && mix test
```

Resolve conflicts before the next merge. Dependent tasks in the next wave are run
with `base_branch = integration/<run-id>/wave-<k>` so they build on the integrated
result, not on stale `main`.

## The ledger (the skill writes it; the script never does)

Workflow scripts have no filesystem access and cannot read the clock, so the
**skill** writes `.orchestrator/fleet.json` and stamps timestamps after each wave
returns. Minimum per-checkpoint fields (from the wave-result): `task_id`, `branch`,
`commit`, `produced_contract`, `review` verdict, `verification` evidence,
`known_limitations`, `status`. Append wave-level `techdebt[]` entries to
`techdebt.md`. Treat `.orchestrator/fleet.json` as the run's state; add
`.orchestrator/` to `.gitignore` in a real repo.

## Verifying / building a branch yourself

Any fresh checkout is **deps-bare** — always `mix deps.get` first:

```bash
git worktree add ../verify-<id> <branch>           # scratch checkout of a committed branch tip
cd ../verify-<id> && mix deps.get && mix test       # reproduce evidence independently
```

## Final PR review

```
/review <PR-number>
```
Run after `FinalMerge.md` opens the release PR (Phase 6).
