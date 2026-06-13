# FinalMerge (Phase 6) — global seam gate

The final phase, run **by the skill (the agent), in the main loop** — there is no
separate cmux merge instance and no Codex. Once every wave is integrated and
verified, the agent turns the latest wave-integration branch into one release
branch + PR. This phase is a **global seam gate**: it checks cross-wave coherence,
unresolved seam obligations, checkpoint evidence, and release readiness. It does
**not** re-litigate every task from scratch (each task was already reviewed and
verified inside its wave by `workflow-scripts/wave-runner.js`).

## Preconditions
- All `fleet/<run-id>/task/N-<slug>` branches reached `checkpoint_ready` in their
  wave and were merged into their wave-integration branch (Section 2 of
  `RunTaskFleet.md`).
- `.orchestrator/fleet.json` records the approved DAG, checkpoints (commit, produced
  contract, review verdict, verification evidence, known limitations), soft-edge
  seam obligations, and each wave's integration branch.
- Know the **base branch** the run was cut from (often `main`; may be an active
  feature branch — do **not** assume `main`; read `base_branch` from the ledger).

## Step 1 — Create the release branch
The agent does this directly with git (no cmux instance):
```bash
git checkout integration/<run-id>/wave-<last>      # the latest VERIFIED wave integration
git checkout -b release/<goal-slug>
mix deps.get && mix compile --warnings-as-errors && mix test   # baseline: the integrated tree is green
```
If the integrated tree is not green here, that is a cross-wave seam failure — go to
Step 3's disposition loop before proceeding.

## Step 2 — Check global seams against the ledger
Read `.orchestrator/fleet.json` and confirm, for the release tree:
- every **blocking checkpoint** is still represented (no wave integration silently
  dropped a produced contract);
- every unresolved or high-risk **`soft_edges` seam obligation** is checked: shared
  files, public function/module contracts, API/schema shapes, route/layout coupling,
  auth/data assumptions, shared test utilities, UX consistency.
Spawn a Claude subagent to investigate any seam you cannot confirm by reading the
diff; adopt its finding and continue.

## Step 3 — Merge-seam review panel (Claude-only) + disposition
Run a **review panel on the release diff**, weighted toward **cross-wave
interaction** (not re-reviewing each task). Use the same mechanism as a wave's
review stage — either:
- a small `Workflow` that fans out the lenses in `parallel()` and returns
  schema-validated, deduped findings (preferred for >2 lenses), or
- direct Claude subagents, one per lens, for a quick panel.

Lenses: **C, CM, P** with an explicit *merge-seam* focus; add **S/O** only if the
ledger flags security or operability seam risk. Merge + dedupe with provenance
(`references/review-verification.md`).

**Disposition** every finding (`references/review-verification.md`):
- **ACCEPT** → fix now (a Claude subagent in a worktree on `release/<goal-slug>`,
  committed); re-review the patched tree. Cap the loop at 3 rounds; at the cap with
  ACCEPT remaining, escalate to one higher-effort Claude rescue subagent, then to a
  conscious orchestrator decision (re-scope / downgrade / surface to the user).
- **FIX_LATER** → append to repo-root `techdebt.md` (dated convention in
  `references/review-verification.md`). **Does not block the PR.**
- **DEFER** → note in the final summary.

## Step 4 — Orchestrator arbiter pass + PR
The agent is the final arbiter; this is a real gate, not a glance. Re-read the
release diff and the ledger and confirm: (a) every checkpoint remains represented;
(b) no produced contract was dropped in integration; (c) all soft-edge seam
obligations are resolved or consciously logged; (d) all ACCEPT findings are resolved
and FIX_LATER items are in `techdebt.md`.

- **Gate:** if any of (a)–(c) fails, return to Step 3 (fix + re-review) before
  opening the PR. If only FIX_LATER debt remains, pass — it is logged, not blocking.
- Then open the PR against `<base-branch>` and run the GitHub multi-agent review:
```
/review <PR-number>
```

## Step 5 — Teardown
Remove every engine-created worktree (they **persist** once they hold a commit) and
the task/integration branches no longer needed. The skill owns this:
```bash
git worktree list                                   # find leftover fleet worktrees
git worktree remove --force <each fleet/integration worktree>
git worktree prune
git branch -D fleet/<run-id>/task/<N>-<slug>         # per task, after the PR captures the work
git branch -D integration/<run-id>/wave-<k>          # per wave
```
`.orchestrator/fleet.json` is a transient run artifact — keep it for the run's
record or delete it; if the skill is used in a real repo, add `.orchestrator/` to
`.gitignore`.

## Output
- One `release/<goal-slug>` branch off the latest verified wave integration,
  containing all tasks, seam-reviewed + dispositioned, PR-reviewed via `/review`.
- A final report: waves integrated, seam obligations checked, panel verdicts,
  FIX_LATER debt logged to `techdebt.md`, leftover risks.
- Cleaned-up worktrees and branches.
