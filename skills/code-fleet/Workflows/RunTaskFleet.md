# RunTaskFleet Workflow (hybrid)

Decompose a goal into N task nodes, build a dependency graph, and run each ready
set as **one native Workflow call** whose pipeline carries every task through
`work → review → fix → verify` in an isolated git worktree. The orchestrator
(this skill) coordinates; it does not do the task work itself.

This workflow is **two layers that compose**:

- **The skill is the cross-process scheduler** (policy / governance). It owns
  decomposition into a DAG, thought-level calibration, **user approval of the
  DAG**, and — for each wave — the single Workflow call, then wave integration
  (ledger write, one-branch-at-a-time merge, seam check), then the handoff to
  the `FinalMerge.md` global seam gate.
- **The native Workflow is the in-process executor** (per-wave fan-out). One
  call per ready set runs `pipeline(work, review, fix, verify)`, one item per
  task, each worker in **isolation worktree mode**.

The load-bearing reason the skill still exists: **a Workflow runs to completion
with no mid-run user input.** The mandatory DAG-approval gate (and any
reapproval event) therefore lives in the skill loop **between** per-wave
Workflow calls. It cannot live inside a workflow script.

**What changed from the manual loop.** The old per-task
cmux/worktree/`wait-for` inner loop is gone. There is no `cmux new-workspace`,
no `cmux send`, no namespaced `wait-for` wake token, and no Codex. The wave
Workflow's `agent(prompt, {schema})` calls replace cmux workers; its barrier
(`pipeline` completion) replaces the `wait-for` bridge; and the **review panel
is now parallel Claude lens subagents inside the Workflow**, each carrying one
distinct skeptical lens.

**Section labels below:** `0 / 0.25 / 0.5` are skill *setup* steps; Section `1`
is the per-wave Workflow call; Section `2` is skill-owned wave integration. The
pipeline *stages* inside the Workflow map to the canonical Phases (work=1,
review=2, fix=3+4, verify=5); Phase 6 merge lives in `FinalMerge.md`.

## Contracts pinned by this document

Three contracts are easy to drift across the skill, the JS wave script, and
`references/review-verification.md`. They are pinned **once, here**, and every
other section defers to these names. The JS wave script is the source of truth
for shapes the script emits; this section restates them so the skill reads
exactly what the script writes.

- **Isolation mechanism (ADR 0003 — verified live; the `workspace:{mode}` option
  is INERT and removed).** There is no `workspace`/`worktree` agent option that
  the runtime honors.
  - **Write stages (work, fix, rescue)** pass the real workflow flag
    `isolation: "worktree"`. The runtime hands the agent a fresh worktree on an
    **engine-auto-named** branch; the brief then `git checkout -b
    fleet/<run-id>/task/<N>-<slug>` (worker) or `git checkout <that branch>`
    (fix/rescue) and commits there. The named branch is what wave integration
    merges by name.
  - **Read stages (review, verify)** take **no** isolation flag. The brief reads
    the committed branch tip from the shared git object store
    (`git diff <base>...<branch>`, `git show <branch>:<file>`, or a scratch
    `git worktree add ../verify-<id> <branch>` when it needs to build/run).
  - **Fix subagents run sequentially**, not in parallel: one branch cannot be
    checked out in two worktrees at once, so each ACCEPT fix commits to the
    branch before the next begins (tasks across the wave still pipeline; only
    fixes *within* a task serialize).

- **No stale-state verify.** Because every fix/rescue **commits** to the named
  branch and the gates read the **committed branch tip** (not a scratch tree),
  the verifier always sees the fixes. The rule the briefs bake in: *a change is
  invisible to review/verify until it is committed to the named branch* — commit
  everything that matters.

- **Worktree teardown is skill-owned.** Isolation worktrees **persist** once they
  hold a commit (verified). The skill removes them at integration/teardown (2c)
  with `git worktree remove --force` + `git branch -D` for branches not kept.

- **Finding record (one schema, `refuted` not `found`).** Lens subagents return
  records matching `references/review-verification.md`'s PanelFindings exactly.
  The single `FINDINGS_SCHEMA` is:

  ```jsonc
  {
    "lens": "C",                 // which lens raised it (C, CM, P, E, S, D, …)
    "refuted": false,            // true = this lens actively looked IN SCOPE and
                                 //        found nothing to report (a clean refute).
                                 // false = the records[] below carry real findings.
    "records": [
      {
        "severity": "major",     // blocking | major | minor | nit
        "confidence": "high",    // high | medium | low — feeds disposition policy
        "file": "lib/…",
        "line": 0,
        "finding": "…",
        "suggested_fix": "…"
      }
    ]
  }
  ```

  `refuted: true` with empty `records` is the canonical "nothing in this lens"
  result (it proves the lens looked, vs. silence). **There is no `found`
  field** anywhere — the older `found` boolean is retired.

- **Disposition: policy proposes, judgment confirms.** After dedupe, the script
  calls a deterministic `proposeDisposition(record)` (severity × confidence) to
  suggest `ACCEPT | FIX_LATER | DEFER`, then `resolveDisposition` finalizes it —
  honoring an ACJ Judge's `judge_disposition` when present (L4 / contested
  findings), otherwise keeping the proposal. Every merged finding therefore
  carries an authoritative `disposition` field (severity enum
  `blocking | major | minor | nit`, confidence `high | medium | low`).
  Single-lens vs. multi-lens provenance feeds the confidence the proposal reads.
  A further human-judgment override can still happen **in the skill** at 2b when
  arbitrating `needs_orchestrator` (it may consciously downgrade an ACCEPT to
  FIX_LATER).

- **Status enum (one set of three).** Per-task status is exactly one of
  `"checkpoint_ready" | "held" | "needs_orchestrator"` — the values the JS
  script's `toTaskResult` emits. There is **no** `green`/`failed`:
  - `checkpoint_ready` — verify PASS and no ACCEPT findings remain (this is
    "green" in prose).
  - `needs_orchestrator` — the fix stage hit the cap with ACCEPT remaining (or
    rescue still failing), **or** verify FAIL; the skill must arbitrate.
  - `held` — a blocking upstream did not reach `checkpoint_ready`, so this task
    was not run / not admitted; the skill holds it (2b).

- **Techdebt lives at the WAVE level.** The wave-result carries a single
  top-level array field named **`techdebt`** (the script `flatMap`s per-task
  FIX_LATER and DEFER records up to the wave). Each entry is
  `{ task_id, branch, file, line, finding, lenses, disposition, reason }` —
  `lenses` is an **array** (provenance), `disposition` is `FIX_LATER | DEFER`
  (ACCEPT items are fixed, never debt), `reason` is why it is non-blocking. The
  skill prints these to `techdebt.md` using
  `references/review-verification.md`'s dated convention, rendering the `lenses`
  array into the doc's single `(lens: …)` note by joining with `+`
  (e.g. `(lens: C+P)`).

- **Re-review cap = "exactly N rounds", `round < cap`.** The fix loop is
  `while (hasAccept && round < cap) { fix; round++; re-review }`. With the
  loop guard `round < cap`, the body runs **at most `cap` times** — exactly N
  re-review rounds, never N+1. Rescue fires **after** the loop if ACCEPT still
  remains. (`cap` is the level's count: L1=1, L2=2, L3=3, L4=3.) This is the
  single authoritative boundary; ignore any `round > cap` / `while(true)`
  phrasing elsewhere.

## Steps

### 0. Preflight
```bash
git status                             # repo must be clean-ish; stash/commit stray work first
git worktree list                      # see what already exists; engine worktrees persist once they hold a commit
git branch --list 'fleet/*'            # check for leftover task branches from a prior run
```
- No `cmux ping` and no `/codex:status`: the hybrid uses native Workflows for
  execution and Claude subagents for review. There is nothing external to
  health-check here.
- Decompose the goal into discrete task nodes **sized to ~1–2 hours each**
  (split anything bigger — `references/orchestration-principles.md`). Give each
  task a short `slug`.
- **Resource Inventory (mandatory for UI/design work — see
  `references/review-verification.md`).** Before writing the task specs, spawn a
  Claude subagent to survey what already exists, so tasks aren't built blind to
  in-repo standards:
  ```
  Agent(general-purpose, label="resource inventory"):
    "Survey reusable assets for these tasks: (1) the project design SOP (look for ai_docs/design-sop.md or equivalent);
     (2) the canonical in-app design source — the /design route and the component it renders (e.g. DesignThemePage.tsx) —
     and list the reusable components/patterns it already implements; (3) shared components in web/src/components/;
     (4) the layout contract (wireframe HTML) and which anchor maps to each task.
     For EACH task, return: surface-type classification, the exact components/patterns to REUSE (with file:symbol), and any
     superseded file that must be REPLACED wholesale. Do not implement anything."
  ```
  Fold the result into each task spec as an **"Existing resources to reuse"** +
  **surface-type** block. If the repo has no design-SOP doc yet but a design
  system clearly exists, note that the SOP should be codified — an uncodified
  standard can't be enforced.

### 0.25 Dependency Graph (mandatory, before any worker spawn)
Run `Workflows/DependencyGraph.md` before thought-level calibration. This is the
parallelism gate.

1. Spawn the dependency-mapper subagent described in `DependencyGraph.md`.
2. As orchestrator, arbitrate its output into:
   - task nodes
   - `blocking_edges`
   - `soft_edges`
   - wave groups (each wave is one ready set)
   - seam obligations
   - the checkpoint bundle each task must produce
3. Persist `.orchestrator/fleet.json` with a unique `run_id`. **The skill writes
   this file**, not a workflow script — scripts have no filesystem access. Use a
   `run_id` you generate here in the skill loop (workflow scripts cannot call
   clock/randomness builtins, so they can never mint a `run_id`).
4. Show the user a wave table plus blocking/soft edge rationale and **wait for
   approval**.
5. **Do not call the first wave's Workflow until the user approves the DAG.**

After approval, execute autonomously unless a **Reapproval Event** (material
contract change, new blocking edge, task split, or risk-level increase)
invalidates the approved graph (Section 2d). Normal implementation details do
not require reapproval.

### 0.5 Thought-Level Calibration (per task, before any spawn)
Don't blanket-max. For each task, spawn an **assessor subagent** (advisory —
keeps spec-reading off the orchestrator's main context):

```
Agent(general-purpose, label="assess task N"):
  "Read this task spec: <path to NN-slug.md>. Skim the files it lists under 'Required Reading'
   enough to judge difficulty — do NOT implement anything.
   Score 5 axes 0/1/2 and return STRICT JSON {A,B,C,D,E,sum,level,split_recommended,rationale}:
     A spec_clarity   (INVERTED: 0 fully spec'd w/ anchors → 2 vague)
     B impl_complexity (0 render static markup → 2 nontrivial state/logic/async)
     C blast_surface  (0 owns one file → 2 touches shell + shared components + routing/data)
     D verify_surface (0 static snapshot → 2 multi-step interactive flow)
     E precedent      (INVERTED: 0 clear in-repo pattern to mirror → 2 novel)
   level: sum 0–2 L1 | 3–5 L2 | 6–7 L3 | 8–10 L4.  split_recommended=true only if L4."
```

Map the returned level to the worker's knobs (orchestrator may override —
document why). The panel is now **Claude lens subagents**, but the lens counts
are unchanged:

| Level | Worker effort | ultrathink in brief | Review panel (Claude lenses) | Re-review cap | Verify |
|-------|---------------|---------------------|------------------------------|---------------|--------|
| **L1** | medium | no  | 1 lens (C; B if maintainability-dominant) | 1 | read branch-ref diff/output only |
| **L2** | high   | yes | 3 lenses (C+CM+P) | 2 | diff/output + 1 build/test run |
| **L3** | high   | yes | 5 lenses (+E+S) | 3 | full build + targeted test run of the flow |
| **L4** | max    | yes | 8 lenses + ACJ debate (3 agents) | 3 | full build + orchestrator arbiter pass |

- **ACJ at L4 is three more Claude subagents**, not one judge: an **Advocate**
  (argues the contested finding is real and blocking), a **Critic** (argues it
  is not), and a **Judge** (rules ACCEPT/FIX_LATER/DEFER on the contested set),
  per `references/review-verification.md`'s "L4 Advocate-Critic-Judge Debate."
  The Judge's ruling feeds the same `disposition()` reconciliation, it does not
  bypass it. All three count inside the concurrency budget (see the cap note in
  1a) and inside the re-review cap.
- Fixes are **one Claude subagent per ACCEPT finding** (not a level knob); the
  re-review cap bounds the loop, and a **higher-effort Claude rescue subagent**
  is the escalation path at the cap, not an extra round
  (`references/review-verification.md`). Codex rescue is removed.
- **L4 + `split_recommended`:** split the task and re-assess the halves before
  the wave runs, rather than putting an oversized worker into the pipeline.
- Record each task's `{level, override?, rationale}` in the ledger — it drives
  the worker brief and the verify rigor passed into the Workflow.
- Model is **not** calibrated; all workers run on Claude at the calibrated
  effort. Independence in review comes from **diverse lens briefs, not a second
  model.**

### 1. Per-wave execution: one Workflow call per ready set
For each wave in the approved DAG, **in wave order**, the skill makes exactly
one native Workflow call. Everything inside the call runs to completion with no
user input; the skill regains control only when the call returns.

#### 1a. What the skill passes in (ready-set payload)
The skill builds a plain-JS-serializable payload for the ready set and hands it
to the Workflow. It contains everything a worker needs, because the script
cannot read the filesystem or the ledger itself:

```jsonc
{
  "run_id": "20260603-143000",            // minted by the skill in 0.25
  "wave": 2,
  "base_branch": "integration/20260603-143000/wave-1",  // latest VERIFIED wave integration (or base_branch for wave 1)
  "repo_path": "/abs/path/to/repo",
  "tasks": [
    {
      "id": 3,
      "slug": "order-form",
      "level": "L3",
      "effort": "high",
      "ultrathink": true,
      "branch": "fleet/20260603-143000/task/3-order-form",
      "workspace_name": "fleet-20260603-143000-task-3-order-form",   // stable name → runtime derives the worktree path
      "worktree_dirname": "repo-fleet-20260603-143000-task-3-order-form", // skill derives the SAME path for teardown (2c)
      "goal": "…",
      "acceptance_criteria": ["…"],         // the verify stage tests these
      "dag_context": {
        "blocking_satisfied": ["task 1: order API contract @ <sha>"],
        "soft_edges": ["shares layout with task 4 — seam: public props of <Shell>"],
        "produces": "order form checkpoint bundle",
        "downstream_waiting": ["task 7 depends on this checkpoint"]
      },
      "review_lenses": ["C", "CM", "P", "E", "S"],   // count = level (see 0.5); UI adds "D"
      "rereview_cap": 3,
      "resource_block": { /* Existing-resources-to-reuse + surface-type from Step 0 */ }
    }
  ]
}
```

The skill mints `workspace_name` and derives `worktree_dirname` from it with a
fixed rule (sibling of `repo_path`, named `<repo-basename>-<workspace_name>`),
so **2c teardown removes the exact directory the runtime created.** The
`workspace_name` is what the script passes as `workspace.name`; the runtime
derives the on-disk path from it, and the skill's deterministic rule reproduces
that path — the two never diverge.

**Concurrency cap (hard constraint, sized by the skill).** The runtime caps
concurrency at ~16 agents (lifetime ~1000). The wave script does **not**
throttle the inner lens fan-out, so the skill **sizes the ready set** so the
peak agent count stays under the cap. Peak per task during review =
`len(review_lenses)` (+3 for an L4 ACJ debate). The skill admits tasks into a
wave such that the **sum of concurrent peaks** across pipelined tasks ≤ 16; an
L4 UI task alone (8 lenses + D + ACJ = 12) nearly fills the budget and should be
the only heavy task in its wave (or split in the DAG). The outer
`pipeline(..., { concurrency: N })` value the script receives equals the number
of tasks the skill admitted, so the outer pipeline never oversubscribes either.
A wave whose sized peak would exceed 16 must be **split in the DAG**, not crammed
into one call.

#### 1b. The wave Workflow script (`pipeline` of work, review, fix, verify)
The script is **plain JS, no filesystem access, no clock/random builtins.** It
returns structured data only. The skill stamps timestamps and writes the ledger
afterward (Section 2). One `pipeline()` runs each task through the four stages
with **no barrier between stages** (a fast L1 task can finish verify while an L3
task is still in work); the `pipeline` call itself is the barrier that returns
control to the skill once every item has cleared verify or stalled.

The executable script is **`workflow-scripts/wave-runner.js`**, a self-executing
workflow body (ADR 0003): it defines `runWave(wave)` + `describe()` and ends with
a tail that reads the runtime global `args` and dispatches (`args.describe` →
self-describe; otherwise `args` **is** the wave payload). `meta.name: "runWave"`.
It is the **single source of truth** for the wave-execution logic — do not
maintain a second copy of its body here.

There is **no `runWorkflow()` primitive.** A skill is markdown the agent follows,
not a program. So *the agent executing this skill* invokes the wave by **calling
the Workflow tool**, once per approved ready set (ADR 0003):

```text
# Per approved wave, in the agent's turn (NOT inside any workflow script):
Workflow({ scriptPath: "<skill-dir>/workflow-scripts/wave-runner.js", args: wavePayload })
#   wavePayload is the 1a payload (the runtime exposes it to the script as `args`).
#   The tool returns the 1c wave-result. If scriptPath is unavailable, fall back to
#   reading the file and passing its body as the inline `script` with the same args.
# The agent then does Section 2 (ledger write, integration) — the script touched no fs.
```

The per-wave "loop" is the **agent driving it turn by turn** — call the Workflow
tool, read the structured result, write `fleet.json`, integrate, then the next
wave — with the approval/integration gates between waves (a Workflow runs to
completion with no mid-run input). To query the contract before the first wave,
the agent can call `Workflow({ scriptPath: …, args: { describe: true } })`.

The script's shape — read it for the full implementation:

- **Stages.** One `pipeline(wave.tasks, [work, review, fix, verify])` with **no
  barrier between stages** (a fast L1 task can finish verify while an L3 task is
  still in work); the `pipeline` call itself is the barrier that returns control
  to the skill once every item has cleared verify or stalled.
- **Isolation (ADR 0003, verified live).** Work/fix/rescue pass the real flag
  `isolation: "worktree"` and the brief `git checkout`s the named branch and
  commits. Review/verify take no flag and read the **committed branch tip** via
  git (`git diff <base>...<branch>` / `git show <branch>:<file>`), so they see
  committed fixes and never verify stale state. Fixes run **sequentially** (one
  branch ≠ two worktrees). Skill removes persisted worktrees at teardown.
- **Disposition (C8).** `proposeDisposition` (severity × confidence) suggests
  `ACCEPT | FIX_LATER | DEFER`; `resolveDisposition` finalizes it, honoring an
  ACJ Judge's `judge_disposition` at L4. Every merged finding carries an
  authoritative `disposition`.
- **Cap (C9).** Fix loop guard is `round < cap` (exactly the level's cap of
  rounds at most: L1=1, L2=2, L3/L4=3) — then one higher-effort Claude rescue,
  then `needs_orchestrator` if ACCEPT still remains.
- **Return (C1/C3).** `runWave` returns `{ run_id, wave, tasks: TaskResult[],
  techdebt }` where each `TaskResult` is shaped per 1c and `techdebt` is the
  **wave-level** flatMap of per-task FIX_LATER/DEFER records. No timestamps, no
  file writes — the skill stamps time and persists in Section 2.

**Stage: work (Phase 1).** The worker brief MUST bake in the proven
isolation-worktree facts (do not let the worker re-derive them):

- "You are in an **isolated worktree** (workspace name `<workspace_name>`) on
  the **named branch** `<branch>`. Commit frequently to that branch —
  integration merges it by name, and **review/verify read the branch tip, not
  your scratch tree.** Uncommitted work is invisible to the gates."
- "**A fresh isolation worktree has NO fetched deps.** Your FIRST `mix compile`
  will fail with *Unchecked dependencies, run `mix deps.get`*. Run **`mix
  deps.get` before any `mix compile` or `mix test`.**"
- "`deps/`, `_build/`, and `mix.lock` are gitignored — **leave them unstaged**
  so wave integration merges stay clean. Stage only source changes."
- The task goal + **explicit, checkable acceptance criteria** (the verify stage
  tests these), the DAG context (blocking satisfied, soft edges/seam
  obligations, produced checkpoint, downstream waiting), and `ultrathink` only
  for L2+.
- **For UI/design tasks:** the "Existing resources to reuse" + surface-type
  block; the three-tier source ranking (canonical `/design` React = reuse;
  wireframe = layout/anchors, wins on conflict; design SOP = rules); the
  replace-don't-accrete mandate; and "your panel includes **lens D (Design SOP)**
  regardless of level."
- "**Do NOT ask the user questions.** Resolve ambiguity yourself or via a
  subagent and document the assumption in your commit." (There is no mid-run
  user channel — the Workflow runs to completion.)

There is **no final `wait-for` signal line** — the `pipeline` barrier is what
returns control to the skill.

**Stage: review (Phase 2) — parallel Claude lens panel.** Codex is removed. The
panel is `parallel()` Claude subagents, **one per lens**, count sized by level
(L1→1 · L2→3 C+CM+P · L3→5 +E+S · L4→8 + ACJ; UI adds D regardless of level),
each reading the **committed branch tip** from git (`git diff <base>...<branch>`,
`git show <branch>:<file>`) — no isolation flag.
Each lens brief is **single-purpose and skeptical**: review the branch-ref diff
**through this lens only**, **try to REFUTE** the worker's claim, and return a
`FINDINGS_SCHEMA` record — either `refuted: true` with empty `records` ("I
looked through this lens and found nothing") or `refuted: false` with one or
more `{severity, confidence, file, line, finding, suggested_fix}`. Merge +
**dedupe with provenance** by `(file, line, finding)`, keeping the `lenses[]`
that raised each record (multi-lens = higher confidence). **Disposition is then
proposed by code policy** (`proposeDisposition`, severity × confidence) and
**finalized by `resolveDisposition`** — which honors an ACJ Judge's ruling at L4
and otherwise keeps the proposal; lenses report defects, they do not triage. At
**L4** the ACJ debate (Advocate + Critic + Judge subagents) rules the contested
subset, and the Judge's `judge_disposition` flows into that reconciliation. Lens
reference: `references/review-verification.md`.

**Stage: fix (Phase 3 + capped Phase 4).** The script reads each merged
finding's resolved `disposition`: **ACCEPT** → one fix subagent per
finding, in parallel, **committed to the branch**; **FIX_LATER** → emitted into
the wave-level `techdebt` array for the skill to append to `techdebt.md`
(the script cannot write files); **DEFER** → also captured in wave-level
`techdebt` (and noted in `known_limitations`). Only
ACCEPT drives the re-review loop, which runs **exactly the level's cap of rounds
at most** (`round < cap`: L1=1, L2=2, L3/L4=3) — **never one more.** With ACCEPT
still remaining after the cap, escalate to **one higher-effort Claude rescue
subagent** (effort `max`), then re-review once. Still failing → the task's status
becomes `needs_orchestrator` so the skill can re-scope, spawn an investigator,
or consciously downgrade to FIX_LATER (Section 2b). ACJ debate (L4) counts inside
the cap and the concurrency budget.

**Stage: verify (Phase 5) — independent gate.** A separate Claude subagent
independently verifies the task did what the worker claimed; it does **not**
trust the self-report. It checks out the **committed branch tip** itself
(`git worktree add ../verify-<id> <branch>`), which contains every committed fix,
so it never verifies stale state. At the calibrated rigor: read the branch diff and run
the real `mix deps.get` / `mix compile` / `mix test` (a shared checkout is also
deps-bare, so **run `mix deps.get` first**, no errors swallowed); for L2+ run the
build/tests; for L3 run the targeted flow; for L4 the orchestrator adds its own
arbiter read after the wave returns. UI/design tasks also get a **design audit**
subagent (`Workflows/DesignAudit.md`) — a design FAIL is a verify FAIL. Returns
PASS/FAIL + concrete evidence.

#### 1c. What the Workflow returns (wave-result schema)
The script returns **structured data only** — no timestamps, no file writes.
The skill stamps time and persists it (Section 2). Field names and the status
enum below are **exactly** what `runWave` / `toTaskResult` emit; the skill reads
these names verbatim. Note the contract specifics: the sha field is **`commit`**
(not `commit_sha`) and is `null` unless `status` is `checkpoint_ready`; the
verify record is **`verification` `{reproduced, evidence, ref}`** (PASS/FAIL is
encoded in `status`, not a `verdict` key on the result); the wave-level debt
field is named **`techdebt`** (not `techdebt_entries`).

```jsonc
{
  "run_id": "20260603-143000",
  "wave": 2,
  "tasks": [
    {
      "task_id": 3,
      "slug": "order-form",
      "branch": "fleet/20260603-143000/task/3-order-form",
      "commit": "<sha at the branch tip the gates read; null unless checkpoint_ready>",
      "status": "checkpoint_ready",          // checkpoint_ready | held | needs_orchestrator
      "produced_contract": "order form checkpoint bundle",
      "known_limitations": ["…"],
      "review": { "verdict": "pass", "rounds": 2, "rescued": false, "findings": [] },
      "verification": { "reproduced": true, "evidence": "mix deps.get ok; mix test: 142 passed; route renders …", "ref": "fleet/20260603-143000/task/3-order-form" }
    }
  ],
  "techdebt": [                               // WAVE-LEVEL: flatMap of per-task FIX_LATER/DEFER records
    { "task_id": 3, "branch": "fleet/20260603-143000/task/3-order-form",
      "file": "lib/…", "line": 0, "finding": "…", "lenses": ["P"], "disposition": "FIX_LATER", "reason": "non-blocking: …" }
  ]
}
```

Status semantics (the one enum, from the pinned contracts):
- `checkpoint_ready` — verify PASS, no ACCEPT remaining ("green").
- `needs_orchestrator` — fix hit the cap with ACCEPT remaining / rescue still
  failing, **or** verify FAIL; the skill arbitrates before treating the task as
  a green checkpoint or holding its dependents.
- `held` — set by the skill (not the script) for a task whose blocking upstream
  is not `checkpoint_ready`; such a task is excluded from the wave it would have
  run in. The script only emits `checkpoint_ready` / `needs_orchestrator`; the
  skill writes `held` into the ledger (2b).

### 2. Wave Integration (skill-owned)
The skill regains control when the wave Workflow returns. Everything in this
section is **skill work**, not script work — it touches the filesystem, the git
index, and the clock.

#### 2a. Persist results into `.orchestrator/fleet.json`
Because workflow scripts cannot touch the filesystem or read a clock, **the
skill writes the ledger and stamps timestamps now**, from the returned
wave-result:

- For each task, fold its `task_id`, `commit`, `produced_contract`,
  `review` verdict, `verification` evidence, and `known_limitations` into a
  **checkpoint bundle** in `.orchestrator/fleet.json` (shape per
  `DependencyGraph.md` Step 5). Stamp each with the wall-clock time **here in
  the skill**.
- Append every wave-level `techdebt[]` record to the repo-root
  `techdebt.md` (create with a `# Tech Debt` header if missing) using the dated
  convention in `references/review-verification.md`. Render each entry's
  `lenses[]` array into the doc's single `(lens: …)` note by joining with `+`
  (e.g. `(lens: C+P)`), and use `reason` as the non-blocking justification.
  FIX_LATER **does not block.**
- Mark each task's `status` in the ledger using the unified enum
  (`checkpoint_ready | held | needs_orchestrator`). `cmux read-screen` is gone;
  **the wave-result is the evidence, the ledger is the state.**

#### 2b. Hold dependents on a non-green checkpoint
For any task whose `status` is `needs_orchestrator` (the script never emits a
"failed" status — `needs_orchestrator` is the non-green signal):

- The orchestrator arbitrates `needs_orchestrator` first: re-scope, spawn an
  investigator subagent, or consciously downgrade the stuck finding to
  FIX_LATER (the one human-judgment disposition override; record it in the
  ledger and `techdebt.md`). Only if none resolves a **material** decision does
  it surface a Reapproval Event to the user (Section 2d).
- **Hold every downstream task whose blocking checkpoint depends on the
  unresolved task** — set those tasks' ledger `status` to `held` and **do not
  include their ids in any later wave's ready-set payload** until the upstream
  checkpoint reaches `checkpoint_ready`. Unrelated ready-set tasks in later
  waves may still run. A commit alone never satisfies a blocking dependency;
  only a `checkpoint_ready` bundle does.

#### 2c. Merge one branch at a time
When **every non-held task in the wave is `checkpoint_ready`**
(`wave.ready_for_integration` is true iff no task is `held` or
`needs_orchestrator`), integrate the wave **before** calling the next wave's
Workflow:

```bash
git checkout -B integration/<run-id>/wave-<k> <base-or-previous-wave-integration>
git merge --no-ff fleet/<run-id>/task/3-order-form     # one branch at a time — NEVER octopus
# resolve conflicts, then merge the next branch in the wave
```

- Merge one `checkpoint_ready` branch at a time; resolve conflicts before the
  next merge. `deps/`, `_build/`, and `mix.lock` are gitignored and unstaged, so
  they don't enter these merges.
- Verify every checkpoint bundle the ledger lists for this wave.
- Check all soft-edge **seam obligations** attached to the wave (shared files,
  public props, contracts, route/layout coupling).
- **Teardown after merge (skill-owned).** Engine worktrees persist once they
  hold a commit; the skill cleans them only **after** the branch is merged,
  targeting the **exact** path it derived from `worktree_dirname` (1a) — the
  same path the runtime created from `workspace.name`:
  ```bash
  git worktree remove --force ../<worktree_dirname>     # e.g. ../repo-fleet-<run-id>-task-3-order-form
  git branch -D fleet/<run-id>/task/3-order-form        # after merge confirmed
  ```
- The **next** wave's payload (Section 1a) sets `base_branch` to
  `integration/<run-id>/wave-<k>` — downstream tasks branch (`workspace.base`)
  from the latest verified wave integration, never from the original base.

#### 2d. Reapproval check
A worker discovery surfaced via `needs_orchestrator` or a verify FAIL may be a
**Reapproval Event**: a material API/schema/shared-component/data-model/auth/UX
contract change, a new blocking edge, a task that should be split, or a risk
increase that changes wave ordering. If so, **pause and re-show the revised DAG
for user approval before calling the next wave's Workflow** — this is exactly
why the gate lives in the skill loop between Workflow calls. Normal
implementation details do not require reapproval.

### Loop / handoff to FinalMerge
- When a wave is integrated (`ready_for_integration` was true and the merges
  landed), **call the next ready set's Workflow** (Section 1) with `base_branch`
  set to this wave's integration branch.
- When **all** waves are `checkpoint_ready` and integrated → proceed to
  `FinalMerge.md` (Phase 6), the **global seam gate** (cross-wave coherence, not
  first integration), then `/review`.

## Output
- N isolated worktrees merged and torn down; each task's work committed on its
  `fleet/<run-id>/task/N-<slug>` branch and merged one-at-a-time into
  `integration/<run-id>/wave-<k>`.
- `.orchestrator/fleet.json` containing the approved DAG, waves, checkpoint
  bundles (with skill-stamped timestamps and commit SHAs), seam obligations,
  review rounds, per-task `status` (`checkpoint_ready | held |
  needs_orchestrator`), and verification evidence — written by the skill from
  each wave's structured Workflow result.
- `techdebt.md` updated with every wave-level FIX_LATER entry (rendering
  `lenses[]` as `(lens: …)`).
- A status summary: per-task verdict, wave verdicts, rounds of review, any
  documented assumptions and held dependents.
- Readiness signal to run `FinalMerge.md`.
