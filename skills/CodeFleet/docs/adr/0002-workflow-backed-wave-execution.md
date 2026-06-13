# ADR 0002 — Execute each wave as one native Workflow; keep DAG, approval, and integration in the skill

**Status:** Accepted

> **ADR namespace.** This ADR belongs to the **CodeFleet skill's own `docs/adr/` namespace**. It is *not* part of the Pixir engine's locked ADR set (`pixir/docs/adr/0001..0009`), which independently assigns its own `0002`. The two `0002`s are unrelated and do not contradict each other: Pixir's `0002` governs the Pixir engine; this `0002` governs the orchestrator skill that *drives* Pixir worktrees. Cross-references to Pixir ADRs in this document always say "Pixir ADR NNNN" explicitly. The orchestrator's *own* prior decision — DAG-gated wave scheduling — is this skill's ADR 0001 and is referenced below simply as "ADR 0001."

CodeFleet splits execution into two cooperating layers: the **skill** is the cross-process scheduler that owns policy and governance, and a native Claude Code **Workflow** is the in-process executor that fans a single ready set out across workers. Each wave runs as exactly one Workflow call; the skill keeps everything that must survive between waves — the dependency graph, the user approval gate, wave integration, and the global seam gate. We chose this hybrid over either pure layer because a Workflow enforces concurrency, journaling, and per-wave resume that a hand-rolled fan-out cannot, while a Workflow runs to completion with no mid-run user input and therefore cannot host the mandatory DAG-approval gate; the trade-off is two layers to keep coherent in exchange for an executor that is hard to corrupt and a governance loop that can still pause for the user. This ADR also records the move to a Claude-only run: the adversarial review panel becomes parallel Claude subagents carrying distinct skeptical lenses, and Codex is removed entirely.

## Context

ADR 0001 established that parallelism is dependency-aware wave execution, not free fan-out: build a user-approved DAG, run only the ready set, integrate each wave, and branch dependent work from the latest verified integration. That decision is sound and is preserved here. What it left open was *how each wave is actually driven*.

The original design drove waves imperatively from the skill: spawn one cmux workspace per task, send a brief, arm a background `wait-for` per task, and reconstruct fleet state by reading screens. That mechanism works but is fragile — concurrency is enforced only by the orchestrator's own bookkeeping, completion depends on each worker remembering a final signal line, and the run's truth is scattered across panes and a JSON ledger the orchestrator must keep consistent by hand.

Native Claude Code Workflows offer a stronger executor for the inside of a wave. A Workflow is plain JS that calls `agent(prompt, {schema})` for validated structured results, `parallel()` as a barrier, and `pipeline()` to run items through stages with no barrier between stages, under an enforced concurrency cap (about 16) and lifetime (about 1000 agents). It journals its own progress and can resume. But it carries hard constraints that decide the architecture:

- **A Workflow runs to completion with no mid-run user input.** There is no way to pause inside a script and wait for a human to approve a graph.
- **Workflow scripts have no filesystem access and cannot call wall-clock or randomness builtins** (the date and random APIs are blocked because they break resume). A script can only return structured data.

These constraints are not limitations to route around; they are the reason a two-layer design is correct. The gate that needs a human, and the side effects that need a clock and a disk, must live outside the script.

## Decision

**Each wave runs as exactly one native Workflow call.** Inside it, a `pipeline()` carries one item per task in the ready set through the stages work → review → fix → verify, with no barrier between stages, and each worker agent runs in **isolation worktree mode**. The Workflow returns schema-validated structured data per task conforming to the **wave-result Contract pinned below**.

**The skill is the cross-process scheduler and owns governance.** Between Workflow calls it: decomposes the goal into a DAG with blocking and soft edges; runs thought-level calibration (L1–L4); presents the DAG and **obtains explicit user approval**; then, per wave, invokes the wave Workflow, performs wave integration (git merge one branch at a time, seam check), and advances. After all waves, it runs **FinalMerge** as a global seam gate (not a first integration) and `/review`.

**The DAG-approval gate lives in the skill loop, between per-wave Workflow calls.** It cannot live inside a Workflow script, because a Workflow cannot pause for user input. This is the load-bearing reason the skill still exists and is not absorbed into a Workflow.

**The skill, not the script, performs side effects.** The wave Workflow returns structured data; the skill writes `.orchestrator/fleet.json`, stamps timestamps, and records checkpoint bundles **after** each wave Workflow returns. The ledger shape, the blocking/soft edge classification, the checkpoint-bundle-as-unblock-condition, the ACCEPT/FIX_LATER/DEFER disposition with `techdebt.md`, one-branch-at-a-time wave integration, and FinalMerge as a global seam gate are all preserved from ADR 0001 and the original skill.

**The run is Claude-only.** The Phase-2 adversarial review panel is now parallel Claude subagents, each carrying exactly one distinct lens (correctness, completeness, pattern, edge, security, and so on), each prompted to refute and stay skeptical, each returning schema-validated findings that are deduped with provenance. Independence comes from **diverse lens briefs**, not from a second model. Codex is removed entirely, including codex rescue; rescue at the re-review cap becomes a higher-effort Claude subagent.

**Worker briefs bake in the proven worktree facts.** A fresh isolation worktree has no fetched deps, so every worktree-isolated brief runs `mix deps.get` before `mix compile` or `mix test`. Workers commit to named branches `fleet/<run-id>/task/<N>-<slug>` so integration can address and merge them. `deps/`, `_build/`, and `mix.lock` are gitignored and stay unstaged so wave-integration merges stay clean. Because engine worktrees persist once they hold a commit, the skill's integration/teardown phase owns `git worktree remove --force` plus `git branch -D` **after** merge.

The two layers compose; neither replaces the other. The skill is policy and governance; the Workflow is per-wave execution.

## Contract (normative)

This ADR is the single source of truth for the data that crosses the skill ↔ Workflow boundary. Where the prose drafts in `Workflows/RunTaskFleet.md`, `workflow-scripts/wave-runner.js`, and `references/review-verification.md` disagree, **they conform to this Contract; this Contract does not conform to them.** Every field name, enum, and option key below is binding. Divergences observed during review (status enum, wave-result field names, techdebt shape, lens schema, verify execution mode, isolation option key, ACJ structure, re-review cap, disposition ownership, concurrency) are resolved here once.

### C1. Wave-result schema (Workflow → skill return value)

The wave Workflow returns one object:

```jsonc
{
  "run_id": "string",                 // fleet run id, echoed back
  "wave": 0,                          // integer wave index
  "tasks": [ /* TaskResult, one per task in the ready set */ ],
  "techdebt": [ /* TechDebtEntry, wave-level aggregate (see C3) */ ]
}
```

Each **TaskResult** has exactly these keys (canonical names — *not* `id`/`produced`/`limitations`, and *not* the bare `task_id`/`slug`-only shape):

```jsonc
{
  "task_id": "N",                     // matches DAG node id
  "slug": "short-kebab-slug",
  "branch": "fleet/<run-id>/task/<N>-<slug>",
  "commit": "git-sha-or-null",        // null iff status != "checkpoint_ready"
  "status": "checkpoint_ready",       // see C2 — the ONLY status enum
  "produced_contract": "string",      // what downstream tasks may rely on
  "known_limitations": ["string"],    // non-blocking gaps, prose
  "review": {
    "verdict": "pass | fail",
    "rounds": 0,                      // review rounds actually run
    "rescued": false,                 // true iff rescue subagent was invoked
    "findings": [ /* LensFinding, see C4 */ ]
  },
  "verification": {
    "reproduced": true,               // independent re-run, NOT worker self-report
    "evidence": "string",            // command(s) run + observed result
    "ref": "branch-or-sha verified"  // the exact ref the verifier checked out
  }
}
```

### C2. Status enum (load-bearing)

There is **one** per-task status enum: `checkpoint_ready | held | needs_orchestrator`. Both the JS script's `toTaskResult` and `RunTaskFleet.md` emit and read exactly these three literals; `green` and `failed` are **not** valid status values (`green` is prose for `checkpoint_ready`):

| `status`           | Meaning                                                                 | Skill action                                                   |
| ------------------ | ----------------------------------------------------------------------- | ------------------------------------------------------------- |
| `checkpoint_ready` | Verified green; commit on the named branch; checkpoint bundle complete. | Integrate (merge one branch at a time); unblock dependents.   |
| `held`             | Did not reach green within the re-review cap, even after rescue.        | Do **not** integrate; **hold all dependents** (seam unmet).   |
| `needs_orchestrator` | Blocked on a decision the script cannot make (contract clash, ambiguity). | Surface to the user/skill; resolve before re-running the task. |

The skill's hold-dependents logic keys off `status: "held"` (and `needs_orchestrator`), **not** a `"failed"` literal. The earlier mismatch — script emitting `held` while the skill checked for `failed` — is resolved: `held` is the canonical not-green terminal status and is the trigger for the dependent-hold path. `green` is replaced everywhere by `checkpoint_ready`.

### C3. TechDebt shape and location

TechDebt is reported **at the wave level** in `wave-result.techdebt` (a flat array the skill appends to `techdebt.md` after the wave returns). It is *not* nested per task; each entry carries its own `task_id`/`branch` for provenance. Canonical entry:

```jsonc
{
  "task_id": "N",
  "branch": "fleet/<run-id>/task/<N>-<slug>",
  "file": "lib/...",
  "line": 123,
  "finding": "string",
  "lenses": ["correctness", "edge"],  // ALWAYS an array (even for a single lens)
  "disposition": "FIX_LATER | DEFER", // ACCEPT items are fixed, never debt
  "reason": "why this is non-blocking"
}
```

Field names are pinned: `lenses` (array, never scalar `lens`); `reason` (never `why_nonblocking`). `techdebt.md` renders each entry's lenses as `(lens: a, b)`. `RunTaskFleet.md`'s per-task `techdebt[]` and the scalar `lens`/`why_nonblocking` spellings are superseded.

### C4. LensFinding schema — `refuted`, not `found`

Every lens subagent returns findings under this schema. The boolean is **`refuted`**, matching `review-verification.md`'s PanelFindings; the script's `found` field and `RunTaskFleet.md`'s finding shape (which had neither) are superseded:

```jsonc
{
  "refuted": true,                    // true = this lens actively looked and found nothing in scope
  "severity": "blocking | major | minor | nit",
  "file": "lib/...",
  "line": 123,
  "finding": "string",
  "suggested_fix": "string",
  "lens": "correctness",             // the single lens that raised it (provenance)
  "confidence": "high | medium | low",
  "disposition": "ACCEPT | FIX_LATER | DEFER"  // see C8
}
```

`dedupeFindings` reads `refuted` (not `found`): a lens with `refuted: true` contributes no findings to the merged set but is recorded as having run (for coverage accounting). Deduplication merges duplicate `finding`s across lenses, unioning their `lens` provenance into the `lenses` array used by C3.

### C5. Isolation mechanism — SUPERSEDED by ADR 0003

> **Superseded.** This ADR originally specified a `workspace: { mode: "isolation" | "shared", … }` option on `agent()`. A live wave proved that option is **inert** — the runtime ignores it (it accepts-but-discards unknown agent options). **ADR 0003 is authoritative for isolation.** Summary of the verified mechanism:
>
> - **Write stages (worker, fix, rescue):** pass the real workflow-level flag `isolation: "worktree"`. The runtime creates a fresh worktree on an **engine-auto-named** branch; the stage brief then `git checkout -b fleet/<run-id>/task/<N>-<slug>` (worker) or `git checkout <that branch>` (fix/rescue, which already exists) and commits there. Fix subagents run **sequentially** (one branch cannot be checked out in two worktrees at once).
> - **Read stages (review, verify):** **no** isolation flag. The brief reads the committed branch tip from the shared git object store (`git diff <base>...<branch>`, `git show <branch>:<path>`, or a scratch `git worktree add … <branch>`).
> - Isolation worktrees **persist** once they hold a commit; the **skill** removes them (`git worktree remove --force`) at wave integration/teardown.

### C6. The deps invariant (still in force)

Any stage that lands in a fresh worktree or checks out a fresh ref gets a tree with **no fetched deps**. Therefore **every** stage that builds — worker, fix, rescue, and the review/verify checkouts — runs `mix deps.get` **before** `mix compile`/`mix test`. The deps invariant is universal and verified live (the first `mix compile` on a fresh tree fails with "Unchecked dependencies, run mix deps.get").

Verification is **independent**: it re-runs the test/compile commands and records reproduced `evidence` and the exact `ref`. A worker's self-reported "done" is never sufficient for `checkpoint_ready`.

### C7. L4 Advocate–Critic–Judge debate — three subagents

At L4, contested findings go through **three** distinct Claude subagents — Advocate, Critic, Judge — matching `review-verification.md`. The script's single-`acjJudge()` collapse is superseded: the Advocate argues the finding is real, the Critic argues it is refuted, and the Judge rules. The Judge's ruling sets the finding's `disposition`. This is three agents per contested finding (subject to the concurrency budget in C9).

### C8. Disposition ownership

Disposition (`ACCEPT | FIX_LATER | DEFER`) is assigned by **agent judgment**, not by a code-only severity table and not unilaterally by an upstream worker:

- For a finding raised by a single lens, that lens's review subagent dispositions it with judgment (it is the lead).
- For contested or multi-lens findings at L4, the **Judge** (C7) sets the disposition.
- Severity and confidence (C4) are **inputs** to that judgment, not a replacement for it. The deterministic `disposition()`/`resolveDisposition()` helper in the script may *propose* a default, but an agent confirms or overrides it; the `disposition` field on the LensFinding is the authoritative value the fix/triage loop reads.

`ACCEPT` findings are fixed in the fix stage. `FIX_LATER`/`DEFER` findings become wave-level techdebt (C3).

### C9. Re-review cap and concurrency

**Re-review cap.** The fix loop runs **at most `rereview_cap` review rounds**, then escalates to the rescue subagent: `for (round = 0; round < rereview_cap; round++) { ... }`; if still not green after the loop, run rescue once; if rescue does not reach green, emit `status: "held"`. This pins the boundary (cap rounds, not cap+1) so the JS script and `RunTaskFleet.md`'s inline loop agree.

**Concurrency.** The hard cap is ~16 concurrent agents (Workflow runtime limit). The per-wave agent count is **bounded by the skill, not assumed away**: the skill sizes the ready set so that `Σ over ready tasks (lenses(task) + acj(task)) ≤ 16`, where a UI/L4 task contributes up to 8 lenses + lens D + 3 ACJ agents. The outer `pipeline()` is given `{concurrency: 16}`, and the inner `parallel()` lens fan-out is governed by the skill's ready-set sizing (and a semaphore where a single task's own fan-out would otherwise exceed the cap). "The runtime will queue it" is not relied upon as the sole guarantee.

## Alternatives rejected

**Pure-skill fan-out (no Workflow).** Keep driving each wave imperatively from the skill — spawn workers, arm per-task wake signals, reconstruct state from screens. Rejected because concurrency, journaling, and resume are then the orchestrator's hand-rolled responsibility: the cap is advisory, completion depends on workers remembering a signal, and a crash mid-wave loses in-flight progress that a Workflow would have journaled. The skill is good at governance and bad at being a reliable concurrent executor.

**Pure-Workflow (no governance skill).** Express the whole run as one Workflow graph with `Dependencies:` labels and let it run end to end. Rejected because a Workflow runs to completion with no mid-run user input, so the mandatory DAG-approval gate has nowhere to live; the user would lose the approval, reapproval, and material-contract-change checks that ADR 0001 made non-negotiable. A pure Workflow also cannot write `fleet.json` or stamp timestamps (no filesystem, no clock), so the durable ledger and seam-obligation record would have nowhere to be persisted. Dependencies-as-labels also reduce blocking/soft edge classification to prose the executor is trusted to obey, which is exactly the failure mode ADR 0001 rejected.

**A second model for review independence (keep Codex).** Run the adversarial panel on a different model to guarantee independence. Rejected because the review-slice POC produced usable, non-redundant findings from diverse lens briefs alone, and a second model doubles setup, auth, and runtime surface. Independence is sourced from diverse skeptical lens briefs and the L4 Advocate–Critic–Judge structure (C7), not from model diversity.

The hybrid takes the executor strengths of the Workflow and the governance strengths of the skill, and puts the human gate where a script structurally cannot reach.

## Proof-of-concept evidence

Two end-to-end slices were run before accepting this decision; both passed.

- **Review slice.** A wave Workflow ran the Claude-only adversarial panel: parallel subagents each carrying one distinct lens, each returning schema-validated findings (C4), deduped with provenance. The panel produced usable, non-redundant findings from diverse lens briefs alone — confirming a second model is not required for independence.
- **Write slice.** A worker in isolation worktree mode confirmed isolation, edited files, ran `mix deps.get` then `mix compile`, committed to a named branch `fleet/<run-id>/task/<N>-<slug>`, and that branch was addressable and mergeable from the main checkout.

The write slice surfaced one gotcha now baked into every brief: **a fresh engine worktree has no fetched deps, and the first `mix compile` fails with "Unchecked dependencies, run mix deps.get".** Every brief that checks out a fresh ref — worker, fix, rescue, review, and verify alike (C6) — must run `mix deps.get` before `mix compile` or `mix test`. The slice also confirmed that engine worktrees persist once they hold a commit (they are not auto-cleaned), which is why teardown is owned by the skill's integration phase after merge.

## Consequences

- Concurrency, journaling, and per-wave resume are enforced by the Workflow runtime instead of orchestrator bookkeeping; a wave that crashes mid-flight resumes from its journal rather than from reconstructed screen state.
- The user-approval gate, reapproval rules, and material-contract-change checks survive intact because they sit in the skill loop between Workflow calls.
- `.orchestrator/fleet.json` remains the durable source of orchestration truth, written by the skill from the structured data each wave returns; the executor never touches the disk or the clock.
- Removing Codex simplifies setup and the runtime surface to a single model. Review independence now depends on the quality and diversity of the lens briefs, so brief authoring becomes the place rigor is invested.
- Two layers must stay coherent: **the wave-result schema and the ledger shape are a Contract pinned by this ADR (see Contract, normative).** `RunTaskFleet.md`, `wave-runner.js`, and `review-verification.md` must be reconciled *to this ADR* — not to each other ad hoc. Any field-name, enum, or option-key change is an amendment to this ADR first.
- The original SKILL.md and CONTEXT.md still describe a cmux/Codex runtime; they must be reconciled to this hybrid (native Workflow executor, Claude-only review) so the prose matches the accepted decision.

## References

- ADR 0001: DAG-gated wave scheduler — parallelism is dependency-aware wave execution (this skill's own ADR set).
- `Workflows/DependencyGraph.md` — DAG construction, blocking/soft edges, the approval gate, and the `fleet.json` ledger shape this ADR preserves.
- `Workflows/RunTaskFleet.md` — the per-wave pipeline (work → review → fix → verify) and checkpoint/disposition model; conforms to the Contract above.
- `workflow-scripts/wave-runner.js` — the executable wave Workflow (entry `runWave(wave)`); its `toTaskResult`, `lensRecordSchema`, `dedupeFindings`, `fixStage`, and `acjDebate` conform to C1–C9.
- `Workflows/FinalMerge.md` — the global seam gate that runs after all waves are integrated.
- `references/review-verification.md` — the adversarial lens set, the `refuted` finding record, the L4 Advocate–Critic–Judge debate, and ACCEPT/FIX_LATER/DEFER disposition, now run as Claude-only subagents.
- `CONTEXT.md` — canonical vocabulary (Fleet Run, Ready Set, Wave, Checkpoint Bundle, Seam Obligation, Wave Integration, Global Seam Gate).
- Pixir ADR 0001–0009 — the *engine* decisions (single-process Session, Log-as-truth, etc.); a separate namespace. Pixir's own `0002` is unrelated to this `0002`.
