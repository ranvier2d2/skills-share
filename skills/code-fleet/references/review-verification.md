# Review And Verification

Use this reference when writing worker briefs, deciding review panel size,
dispositioning findings, or verifying whether a task is really green. The fleet
is **Claude-only**: the review panel is a set of parallel Claude lens subagents
run *inside the wave Workflow*, not a second model.

> **One schema, three docs.** This document describes the `FINDING` /
> `PanelFindings` shapes and the disposition rule in prose; the **binding
> contract** is **ADR 0002 (C1–C9)** as implemented by the executor
> `workflow-scripts/wave-runner.js`. This doc and `RunTaskFleet.md` cite those
> field names and enums verbatim. **Where prose disagrees with the ADR/script, the
> ADR wins** (the script is the only executable artifact and is `node --check`
> clean) — this doc has been reconciled to it. The specific reconciliations are
> called out inline below.

## Independent Verification

A worker reporting "done" is a claim, not proof. A task reaches **green**
(`status: "checkpoint_ready"`) only when all three hold:

- the worker says it is done,
- the Claude lens panel has no unresolved blocking **ACCEPT** findings, and
- an **independent verifier** reproduces the behavior with its own evidence.

> **Status enum (load-bearing).** Per-task status is one of
> `"checkpoint_ready" | "held" | "needs_orchestrator"`. There is no `"green"` or
> `"failed"` string in the wave result — "green" is the *human word* for
> `checkpoint_ready`. A task whose dependency did not reach `checkpoint_ready` is
> `"held"`; the skill's hold-dependents logic keys off `"held"`, not `"failed"`.
> A task the fix loop could not close, and that the rescue pass also could not
> close, is `"needs_orchestrator"`. All three docs emit and read exactly this enum.

Spawn a **verifier subagent** per task, as the final stage of the pipeline. It
does **not** trust the worker's self-report. It reads what the worker actually
produced — files written, the commands it ran, and their *real* output — and,
when UI/routes/functionality are involved, drives the running app to confirm the
acceptance criteria behave as claimed. The verifier returns `PASS`/`FAIL` with
concrete evidence (what it saw), not a paraphrase of what the worker said.

### Where verification physically runs (ADR 0003 — verified live)

There is **no** `workspace`/`worktree` agent option the runtime honors (the
`workspace:{mode}` shape an earlier draft used is **inert** — a live wave proved
the runtime discards it). The real, verified mechanism:

```text
work / fix / rescue:  agent(..., { isolation: "worktree" })   # real flag; brief then `git checkout -b/<named branch>` and commits
review / verify:       agent(..., { /* no isolation flag */ }) # brief reads the committed tip from git
```

This resolves the stale-state hazard at the source: fix subagents and the rescue
pass run in an **isolation worktree** and **commit to the named branch**; the
verifier (and the review lenses) then read the **committed branch tip** straight
from the shared git object store — `git diff <base>...<branch>`,
`git show <branch>:<file>`, or a scratch `git worktree add ../verify-<id>
<branch>`. Because the gates read the branch tip — not the worker's scratch tree —
they always see every committed fix. The contract is therefore: **uncommitted
work is invisible to review and verify**; the worker brief states this explicitly.
(Fix subagents run **sequentially** — one branch cannot be checked out in two
worktrees at once.)

Because a **fresh checkout also has no fetched deps**, the verifier must
run `mix deps.get` **before** any `mix compile` / `mix test`, and must confirm the
worker did the same:

- `mix deps.get` ran **before** the first `mix compile` / `mix test` (a fresh
  worktree fails the first compile with "Unchecked dependencies, run
  `mix deps.get`" — a green claim without it is suspect).
- the work is committed to the task's **named branch**
  `fleet/<run-id>/task/<N>-<slug>` (not a detached HEAD), so wave integration can
  merge it.
- `deps/`, `_build/`, and `mix.lock` are unstaged (gitignored) so the branch
  merges clean.

Prefer driven-app evidence over worker self-checks for runtime behavior: a
worker's own shell may falsely report success (or time out) where an independent
drive of the running app still observes the real result.

## Adversarial Review Panel

The panel runs as **parallel Claude lens subagents inside the wave Workflow**.
The workflow's review stage spawns one `agent(prompt, {schema})` call per lens —
`parallel()` is the barrier, so all lenses run concurrently and the stage
returns only when every lens has returned schema-validated findings. There is no
shell dispatch, no `node` companion, and no second model.

Each lens is a **single-purpose, skeptical** reviewer: it sees the working-tree
diff plus the acceptance criteria, is scoped to exactly **one** concern, and is
told to **refute** the implementation — to actively hunt for the way it is wrong
within its lens, and to say so plainly when it finds nothing. The workflow then
merges and dedupes the lens findings with provenance (see below).

### Why diverse skeptical briefs, not a second model

Same-model review **correlates failures**: a single Claude reviewing its own kind
of output tends to share the implementer's blind spots, so naïvely "asking Claude
to review Claude" inflates confidence without adding coverage. Independence here
does **not** come from a different model. It comes from two deliberate moves:

1. **Diverse lens briefs.** Each lens carries a *distinct* mandate (correctness,
   completeness, security, edge/chaos, …) and is forbidden from straying outside
   it. Decorrelation comes from the briefs being orthogonal, not from the
   reviewer being a different system.
2. **Skeptical/refute framing.** Every lens is prompted to *disconfirm* — to
   assume the diff is wrong and produce the evidence — rather than to bless it.
   A lens that finds nothing must explicitly report "nothing in this lens,"
   which is a signal, not silence.

On top of that, apply a **majority-confirm** read at merge time: a finding raised
by multiple independent lenses is high-confidence; a lone-lens finding is treated
as a lead to disposition with judgment, not an automatic blocker. This is how a
single-model panel recovers real independence.

## Lenses

| Lens | Focus |
| --- | --- |
| C - Correctness | Logic, spec alignment, return and contract behavior |
| CM - Completeness | Acceptance criteria, error/empty/loading states, docs |
| P - Pattern Compliance | Conventions, naming, structure, reuse |
| B - Blind / Fresh Eyes | Diff plus acceptance criteria only; maintainability detector |
| E - Edge / Chaos | Nulls, extremes, concurrency, races |
| S - Security | Injection, sanitization, auth/authz, secrets |
| O - Operability | Clean start, env vars, graceful degradation |
| VP - Values & Principles | Repo guardrails such as `CLAUDE.md`, `AGENTS.md`, `AGENTS`/ADR contracts |
| D - Design SOP | UI/design compliance with the project SOP and canonical design source |

Panel size by level:

- L1: 1 lens, usually C or B.
- L2: 3 lenses, C+CM+P.
- L3: 5 lenses, add E+S.
- L4: 8 lenses plus Advocate-Critic-Judge debate.
- UI/design tasks: include D regardless of level; it takes a slot.

### Concurrency: panel size is bounded, the cap is real

Concurrency is a **hard constraint (~16 concurrent agents)**, and the lens
fan-out is the place it can blow up: an L4 UI task is 8 lenses + D + the
verifier, and the ACJ debate adds 3 more — and several such tasks can pipeline at
once. The panel does **not** assume "the runtime will queue it." Two mechanisms
keep the per-wave agent count under the cap:

1. **The skill sizes the ready set.** Before each wave Workflow call, the skill
   bounds the wave so that `Σ (lenses + verifier + any ACJ agents) ≤ 16`. If the
   ready set is too wide, the skill splits it across waves. This is the primary
   control and it lives in the skill loop (the script cannot, since it runs to
   completion with no mid-run input).
2. **The script throttles the inner fan-out.** The wave script passes an explicit
   concurrency bound to the **inner** `parallel()` lens fan-out as well as the
   outer `pipeline()` — not only the outer one — so a single fat task cannot by
   itself exceed the cap. The script treats the runtime queue as a safety net,
   not as the budget.

Both docs must agree the cap is enforced, not assumed.

## Lens Brief Template

Every lens is one `agent()` call. Hold the brief to a single concern, demand the
refute framing, and bind the return shape to the shared schema so the workflow
gets structured, machine-mergeable findings (not prose):

```text
agent(
  "LENS=<C|CM|P|B|E|S|O|VP|D>. You are a SKEPTICAL reviewer with ONE job.
   Review the working-tree diff THROUGH THIS LENS ONLY: <focus>.
   Assume the implementation is WRONG within your lens and find the evidence.
   Stay strictly inside your lens — do not report issues another lens owns.
   Acceptance criteria: <AC>. Diff: <diff>.
   Every real issue = a FINDING record (see schema): {severity, file, line,
   finding, suggested_fix, lens}.
   Found nothing in your lens? Return findings:[] and refuted:true.",
  { schema: PanelFindings }
)
```

### The shared schema (cited by all three docs)

There is **one** finding record. The script's `lensFindingSchema`,
`RunTaskFleet.md`'s `FINDINGS_SCHEMA`, and this doc's `PanelFindings` all refer to
**this** definition. The earlier divergence (`found` vs `refuted`, missing
`suggested_fix`, missing `lens`) is resolved here:

```text
# Per-finding record. This is the canonical FINDING.
FINDING = {
  severity:      "blocking|major|minor|nit",   // ADR C4 enum (NOT low/medium/high/critical)
  confidence:    "high|medium|low",            // feeds the disposition proposal
  file:          string,
  line:          number,
  finding:       string,     // what is wrong, in this lens's terms
  suggested_fix: string,     // required; "" only if genuinely none
  lens:          "C|CM|P|B|E|S|O|VP|D"   // the lens that raised it (provenance)
}
# After merge+disposition each record additionally carries:
#   lenses: ["C","P", …]          // provenance of every lens that raised it
#   disposition: "ACCEPT|FIX_LATER|DEFER"   // proposeDisposition → resolveDisposition
#   judge: "VALID|INVALID|NEEDS_EVIDENCE"   // present only for ACJ-ruled (L4) findings

# Per-lens return shape from one agent() call.
PanelFindings = {
  lens:     "C|CM|P|B|E|S|O|VP|D",
  refuted:  boolean,         // true = lens actively looked and found NOTHING.
                             //        (refuted the hypothesis "there is a defect
                             //         in this lens"). NOT "found", whose polarity
                             //         is the opposite and is hereby retired.
  findings: [ FINDING ]      // empty iff refuted:true
}
```

Two field decisions that the other docs were splitting on, now pinned:

- **`refuted`, not `found`.** The lens-level boolean is `refuted`. `refuted:true`
  means the lens looked and found nothing (coverage achieved). The script reads
  the `refuted` polarity in its dedupe step; do not reintroduce `found`.
- **Provenance is `lens` (scalar) on the *raw* finding, `lenses` (array) after
  merge.** Each *lens* emits a FINDING tagged with its own single `lens`. The
  **merge step** (next section) collapses duplicates and attaches a `lenses`
  array of every lens that raised the same finding. So: scalar `lens` pre-merge,
  array `lenses` post-merge. The techdebt convention below renders the merged
  `lenses` array.

Lens focus prompts (fill `<focus>` per lens):

- **C** — logic, spec alignment, return/contract behavior; `{:ok,_}|{:error,_}` shape, string-keyed Event `data`.
- **CM** — every acceptance criterion addressed; error/empty/loading states; docs.
- **P** — codebase conventions, naming, file structure, reuse of existing modules.
- **B** — judge using ONLY the acceptance criteria; flag anything not understandable from diff+AC without external context.
- **E** — null/empty, extreme values, concurrency, process crashes, races.
- **S** — injection, sanitization, auth/authz, secrets (no secrets in repo; tokens only in `~/.pixir/auth.json`).
- **O** — clean start, env vars, graceful degradation, `mix deps.get` discipline.
- **VP** — repo guardrails: `CLAUDE.md`, `AGENTS.md`, the locked ADRs (Log-as-truth, stateless turns, distinct channels).
- **D** — UI/design SOP compliance (see Design SOP Binding below).

The workflow runs these as one `parallel()` barrier. Each returns its
schema-validated record; nothing polls.

## Merge, Dedupe, And Majority-Confirm

When the `parallel()` barrier returns, the workflow folds the per-lens records
into one finding set:

- **Dedupe** by `(file, line, finding)`.
- **Tag provenance**: attach a `lenses` array — the set of lenses that raised the
  merged finding (this is where scalar `lens` becomes array `lenses`).
- **Confidence**: a finding raised by **multiple** lenses is high-confidence; a
  single-lens finding is a lead, dispositioned with judgment.
- A lens with `refuted:true` and `findings:[]` is recorded as a clean lens for
  that concern — coverage, not noise.

A merged finding therefore looks like:

```text
MERGED_FINDING = {
  severity, file, line, finding, suggested_fix,   // from FINDING
  lenses:       [ "C", "E", ... ],                // provenance (>=1)
  confidence:   "single|multi",                   // multi iff lenses.length > 1
  disposition:  "ACCEPT|FIX_LATER|DEFER"          // assigned per next section
}
```

The workflow returns this merged, provenance-tagged set as structured data. The
**skill** stamps timestamps and writes the fleet ledger after the wave Workflow
returns (the script cannot read wall-clock/randomness); the workflow itself does
not write files.

## Finding Disposition

Every merged finding gets a `disposition` of **ACCEPT / FIX_LATER / DEFER**. The
mechanism is **policy proposes, judgment confirms** — this reconciles the
"code-driven" and "worker/human judgment" views that the drafts disagreed on:

1. **Policy proposes (deterministic, in the script — `proposeDisposition`).** A
   pure function maps `(severity, multi-lens?)` to a default disposition, so the
   common case is reproducible and resume-safe (severity rank
   `blocking`=4, `major`=3, `minor`=2, `nit`=1):
   - severity `blocking` or `major` (rank ≥ 3) → **ACCEPT** (a lone high-severity
     lead is still ACCEPT; judgment may demote it).
   - severity `minor` (rank 2) → **FIX_LATER** by default.
   - severity `nit`, or out-of-task-scope → **DEFER**.
2. **Judgment confirms (`resolveDisposition`).** The proposal is *overridable* by
   an authoritative ruling: at **L4** the ACJ Judge sets `judge_disposition`
   (ACCEPT / FIX_LATER / DEFER) directly and it wins. A single-lens lead may also
   be promoted/demoted with judgment — the worker (or, at L4, the ACJ Judge) may
   promote a lone-lens
   high-severity lead to ACCEPT, or demote a lone-lens medium to DEFER, recording
   why. Multi-lens findings are **not** subject to judgment override; policy stands.

So `disposition` is always present on the merged finding (the loop in
`RunTaskFleet.md` can safely read `f.disposition`), the *value* is computed by
policy, and only single-lens findings admit a recorded judgment override. This is
the single answer to "who assigns disposition": **policy assigns; judgment
adjudicates the single-lens edge.**

Disposition meanings:

- **ACCEPT**: real defect, in scope, blocks correctness; fix now.
- **FIX_LATER**: real but non-blocking; append to `techdebt.md`.
- **DEFER**: out of scope for this task; note and move on.

Only ACCEPT findings drive the fix and re-review loop. Fixes are **one Claude
subagent per ACCEPT finding** (parallel), each making the minimal correct change
**in the task's isolation worktree** and re-verifying it; re-commit to the named
branch after fixes land.

### Re-review cap (one boundary, stated once)

Cap the loop by the task level: **L1 = 1, L2 = 2, L3 = 3, L4 = 3** re-review
rounds. The boundary is **inclusive and zero-based**: rounds are numbered
`0, 1, …`; the loop runs **while `round < cap`** and rescue fires on the round
where `round == cap` (i.e. exactly `cap` review rounds happen, then rescue). Both
the JS script's fix loop and `RunTaskFleet.md`'s inline loop use this same
`round < cap` test — do **not** use `round > cap` (that would run `cap + 1`
rounds before rescue). **Never loop past the cap.**

At the cap with ACCEPT findings still remaining, escalate in this order:

1. **Claude rescue subagent** — spawn one *higher-effort* Claude subagent (max
   effort, ultrathink, broad read scope across the relevant modules and ADRs),
   running **in the same isolation worktree**, and task it with the stuck
   finding(s) only: "Here is the finding the normal fix loop could not close:
   `<finding>`. Diagnose the real root cause and apply the minimal correct fix."
   Run it **once**. This replaces the old codex rescue; rescue is just a more
   thoughtful Claude pass, not a different model.
2. If still failing, the task is marked **`status: "needs_orchestrator"`** and the
   stuck findings are surfaced as structured data. (A Workflow runs to completion
   with no mid-run user input, so this surfacing is consumed by the *skill loop
   between waves*, not inside the script.)
3. The orchestrator resolves autonomously — re-scope the task, spawn an
   investigator subagent, or consciously downgrade the finding to FIX_LATER with
   a logged rationale.
4. Only if none of that resolves it does the orchestrator ask the user.

## L4 Advocate-Critic-Judge Debate

Run ACJ only for L4 tasks or explicit requests, and only for **contested or
high-severity** findings. **It is three more Claude subagents** — Advocate,
Critic, and Judge — and the JS script implements all three (`wave-runner.js`
runs an Advocate and a Critic that feed the Judge; a single collapsed "judge over
contested findings" pass does **not** satisfy this contract). Their three
head-count is included in the per-wave concurrency budget above.

1. **Advocate** argues the implementation is correct, citing code/tests.
2. **Critic** argues it is wrong, surfacing runtime and edge-case failures.
3. **Judge** reads both, rules each contested claim VALID / INVALID /
   NEEDS_EVIDENCE, and sets the disposition directly to ACCEPT / FIX_LATER /
   DEFER (the `judge_disposition` the script's `resolveDisposition` honors).

The Judge verdict **replaces** the policy disposition for those contested
findings (and is the "judgment" authority for single-lens contested findings at
L4). `NEEDS_EVIDENCE` routes the finding back to the verifier for reproduced
evidence before the Judge re-rules. ACJ rounds count inside the task's re-review
cap.

## techdebt.md Convention

FIX_LATER findings are surfaced by the workflow as structured data; the **skill**
writes the dated entry after the wave Workflow returns (the workflow script has no
filesystem access and cannot stamp the date). The rendered `(lens: …)` prints the
merged **`lenses`** array (so a multi-lens deferral shows every lens), joined by
`+` (matching `RunTaskFleet.md` and the script):

```markdown
## <YYYY-MM-DD> - fleet/<run-id>/task/<N>-<slug>
- **<file>:<line>** - <finding>. _Deferred: <one-line reason it is non-blocking>._ (lens: <C+E+...>)
```

The structured FIX_LATER record the skill consumes carries the array, and the
renderer joins it:

```text
TECHDEBT_ENTRY = {
  task_id:       string,
  branch:        "fleet/<run-id>/task/<N>-<slug>",
  file:          string,
  line:          number,
  finding:       string,
  lenses:        [ "C", "E", ... ],   // the merged provenance array (renders as C+E)
  disposition:   "FIX_LATER" | "DEFER",   // ACCEPT items are fixed, never debt
  reason:        string               // one-line reason; renders after "Deferred:"
}
```

This pins the field names the drafts split on: provenance is **`lenses`** (array,
matching the merged finding) and the non-blocking justification is **`reason`**
(ADR C3 — never `why_nonblocking`). Append; never rewrite history.

## Wave Result Shape (what the workflow returns to the skill)

So the skill can read **one** contract, the wave Workflow returns exactly these
keys (ADR 0002 C1/C3). This is the single agreed shape; the JS `runWave` /
`toTaskResult` and `RunTaskFleet.md` section 1c both produce/consume **this**, not
two variants:

```text
WAVE_RESULT = {
  run_id: string,
  wave:   number,
  tasks: [
    {
      task_id:           string,    // canonical; not "id"
      slug:              string,
      branch:            "fleet/<run-id>/task/<N>-<slug>",
      commit:            string | null,   // branch-tip sha; null unless checkpoint_ready. NOT "commit_sha"
      status:            "checkpoint_ready" | "held" | "needs_orchestrator",
      produced_contract: string,    // canonical; not "produced"
      known_limitations: [ string ],// canonical; not "limitations"
      review:            { verdict: "pass"|"fail", rounds: number, rescued: boolean, findings: [ MERGED_FINDING ] },
      verification:      { reproduced: boolean, evidence: string, ref: string }  // NOT "verify"; PASS/FAIL lives in status
    }
  ],
  techdebt: [ TECHDEBT_ENTRY ]   // WAVE-level field named "techdebt", flattened across tasks
}
```

Field-name reconciliation, stated once: use **`task_id`** (not `id`),
**`commit`** (not `commit_sha`), **`produced_contract`** (not `produced`),
**`known_limitations`** (not `limitations`), **`verification`** (not `verify`),
and collect techdebt at the **wave level** in the field named **`techdebt`** (not
`techdebt_entries`; the script's `results.flatMap(...)`), each entry being a
`TECHDEBT_ENTRY`. The skill never has to read two contracts.

## Design SOP Binding And Resource Inventory

For UI/design tasks, do a resource inventory before writing task specs. The
task spec must include:

- the project design SOP, if present
- the canonical in-app design source, such as a `/design` route
- reusable shared components
- a source ranking: canonical implementation, wireframe/layout anchors, then
  design rules
- a replace-don't-accrete mandate when an existing page is superseded

UI tasks always run **lens D** in the panel and a **design-auditor subagent** in
the verify stage (a second, design-focused Claude subagent that grades the
rendered result against the project's design SOP, not just "does it render"). The
auditor returns PASS/FAIL plus a per-rule violation list; a design-audit FAIL is
treated like a verifier FAIL and bounces the task back through disposition and
re-review. See `Workflows/DesignAudit.md`.
