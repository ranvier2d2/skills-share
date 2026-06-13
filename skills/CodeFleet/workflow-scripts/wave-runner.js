// wave-runner.js  (the wave Workflow — invoked once per ready set by the skill)
// ---------------------------------------------------------------------------
// Per-wave executor for the hybrid CodeFleet.
//
// This is the IN-PROCESS half of the two-layer architecture. The SKILL is the
// cross-process scheduler (decompose -> DAG -> USER APPROVAL -> per-wave run ->
// wave integration -> FinalMerge seam gate -> /review). This script is the
// per-wave fan-out: the skill invokes it exactly ONCE per ready set, and it
// pipelines every task in that wave through the canonical phases:
//
//   Phase 1 Work  ->  Phase 2 Adversarial Review  ->  Phase 3 Disposition+Fix
//                 ->  Phase 4 Re-review (capped)   ->  Phase 5 Verify
//
// CONTRACT SOURCE OF TRUTH: docs/adr/0002-workflow-backed-wave-execution.md,
// the normative Contract section C1-C9. Where RunTaskFleet.md and
// references/review-verification.md disagree with the ADR, the ADR wins and this
// file conforms to the ADR. Specific reconciliations:
//
//   * Entry point is `runWave(wave)` taking the ready-set payload as its single
//     argument (RunTaskFleet 1a/1b), NOT a module-level `args`/`run()` pair.
//   * C1 TaskResult keys: { task_id, slug, branch, commit, status,
//     produced_contract, known_limitations, review{verdict,rounds,rescued,findings},
//     verification{reproduced,evidence,ref} }. `commit` (ADR C1) — NOT `commit_sha`;
//     `verification` (ADR C1) — NOT `verify`. No `id/produced/limitations` aliases.
//   * C2 status enum: ONLY { checkpoint_ready | held | needs_orchestrator }.
//     There is NO `green` literal anywhere — green is prose for checkpoint_ready.
//   * C3 techdebt: WAVE-LEVEL top-level array on the run() return (ADR C1 names
//     the field `techdebt`; the prose docs call it `techdebt_entries` — the ADR
//     field name `techdebt` is authoritative). Each entry:
//     { task_id, branch, file, line, finding, lenses[], disposition, reason }.
//   * C4 LensFinding uses `refuted` (NOT `found`); each finding carries `lens`
//     (scalar, provenance), `severity`, `confidence`, `suggested_fix`,
//     `disposition`. Merged findings carry `lenses[]` (array provenance).
//   * Isolation (ADR 0003, verified live; the old workspace:{mode} option is
//     INERT and removed): work/fix/rescue use the real workflow flag
//     isolation:"worktree" + an in-brief `git checkout -b/<branch>` to the named
//     branch; review/verify use NO flag and read the committed tip via
//     `git show <branch>:<path>`. Fix subagents run SEQUENTIALLY (one branch
//     cannot be checked out in two worktrees at once).
//   * C7 ACJ debate = THREE subagents (Advocate, Critic, Judge) on contested
//     findings; the Judge sets the disposition.
//   * C8 disposition ownership = policy proposes, judgment/ACJ confirms; the
//     `disposition` field on each finding is the authoritative value.
//   * C9 re-review cap: at most `rereview_cap` rounds (round < cap), then ONE
//     rescue, then re-review once; still red -> status "needs_orchestrator".
//     Outer pipeline concurrency is the skill-sized ready-set width; inner lens
//     fan-out is governed by a global AGENT_CAP semaphore.
//
// Hard runtime constraints this file is built around (all verified):
//   * A Workflow runs to completion with NO mid-run user input. The mandatory
//     DAG-approval gate therefore lives in the SKILL loop BETWEEN waves, never
//     here. This script assumes the wave it received is already approved.
//   * Workflow scripts are plain JS, have no filesystem access, and cannot call
//     wall-clock / randomness builtins (Date.*, Math.random) because that breaks
//     resume. This script writes nothing and stamps no timestamps: it returns
//     pure structured data; the SKILL persists .orchestrator/fleet.json and
//     stamps timestamps AFTER this call returns.
//   * agent(prompt, { schema }) returns schema-validated structured data.
//     parallel(items, fn) is a barrier. pipeline(items, ...stages) runs each
//     item through the stages with no barrier between stages.
//
// CLAUDE-ONLY. There is no Codex. The Phase 2 adversarial panel is parallel
// Claude lens subagents, each carrying ONE distinct skeptical lens; independence
// comes from DIVERSE LENS BRIEFS, not a second model. The cap-time rescue is a
// higher-effort Claude subagent, not a Codex rescue.
//
// Determinism: every id, branch, and worktree name is derived from the inputs
// (wave.run_id + task ids). Nothing here reads the clock or rolls dice.
// ---------------------------------------------------------------------------

export const meta = {
  name: "runWave",
  description:
    "Run one approved ready set (wave) of the fleet. Pipelines each task through work (isolation-worktree implementation on fleet/<run-id>/task/<N>-<slug>), adversarial review (parallel skeptical Claude lens subagents on the committed branch tip, deduped with provenance), disposition+fix (one subagent per ACCEPT finding, re-review capped by level, L4 ACJ trio on contested findings), and independent verification (PASS/FAIL on the committed branch). Returns the wave-result per ADR 0002 C1-C9; the skill stamps timestamps and writes fleet.json.",
  phases: [
    { id: 1, name: "Work", owner: "worker", gate: "Task committed to its named branch" },
    { id: 2, name: "Adversarial Review", owner: "lens panel", gate: "Findings harvested + deduped" },
    { id: 3, name: "Disposition + Fix", owner: "fix subagents", gate: "ACCEPT fixed, FIX_LATER logged, DEFER noted" },
    { id: 4, name: "Re-review", owner: "lens panel", gate: "No remaining ACCEPT within the level cap" },
    { id: 5, name: "Verify", owner: "verifier", gate: "Independent PASS evidence captured on the committed branch" },
  ],
};

// ---------------------------------------------------------------------------
// Level matrix (calibrated by the skill in Phase 0.5; this script never
// re-derives it, it only consumes task.level). UI/design tasks always add lens
// D and a design-audit verifier slot regardless of level.
// ---------------------------------------------------------------------------

const LENS_SETS = {
  L1: ["C"], // correctness only (or B if the task is maintainability-dominant)
  L2: ["C", "CM", "P"], // + completeness + pattern
  L3: ["C", "CM", "P", "E", "S"], // + edge/chaos + security
  L4: ["C", "CM", "P", "E", "S", "O", "VP", "B"], // full 8 panel, then an ACJ trio on contested findings
};

// C9 re-review cap = the maximum number of review rounds (round < cap).
// L1=1, L2=2, L3=3, L4=3. ACJ at L4 runs inside this budget — it adds no round.
const RE_REVIEW_CAP = { L1: 1, L2: 2, L3: 3, L4: 3 };

const VERIFY_RIGOR = {
  L1: "read_only", // confirm files/tests from reproduced evidence, no browser
  L2: "snapshot", // evidence + one browser snapshot
  L3: "browser_flow", // drive the full flow in a browser
  L4: "browser_flow_plus_arbiter", // full drive + an arbiter read of the diff
};

const LENS_FOCUS = {
  C: "logic, spec alignment, return/contract behavior",
  CM: "every acceptance criterion, error/empty/loading states, docs",
  P: "codebase conventions, naming, structure, reuse of existing modules",
  E: "nulls, empties, extreme values, concurrency, races, message-order",
  S: "injection, sanitization, auth/authz, secrets, unsafe atom/term creation",
  O: "clean start, deps fetched, env/config, graceful degradation",
  VP: "repo guardrails: CLAUDE.md / AGENTS.md / ADRs / CONTEXT.md vocabulary",
  B: "diff + acceptance criteria ONLY; flag anything unintelligible without external context",
  D: "design SOP compliance, canonical-component reuse, exact-layout match, superseded code removed",
};

// ---------------------------------------------------------------------------
// Concurrency governor (C9). The runtime caps live agents at ~16; pipeline()
// only throttles the OUTER per-task fan-out, not the inner parallel() lens
// panels. We wrap EVERY agent() call in a counting semaphore so the wave never
// exceeds AGENT_CAP concurrent agents even when several L4 panels overlap. This
// is belt-and-suspenders with the skill sizing the ready set.
// ---------------------------------------------------------------------------

const AGENT_CAP = 16;
let _live = 0;
const _waiters = [];

function _acquire() {
  if (_live < AGENT_CAP) {
    _live += 1;
    return Promise.resolve();
  }
  return new Promise((resolve) => _waiters.push(resolve));
}

function _release() {
  _live -= 1;
  const next = _waiters.shift();
  if (next) {
    _live += 1;
    next();
  }
}

// ---------------------------------------------------------------------------
// Dry-run (ADR 0005: every command is dry-runnable). When the wave carries
// dry_run:true, runWave walks the ENTIRE pipeline control flow — same stages,
// same fan-out, same branch/worktree naming, same disposition policy — but every
// model call returns a schema-shaped STUB instead of hitting agent(). No model
// tokens, no worktrees, no mix, no commits. It is the free local test harness:
// it exercises the pipeline()/parallel() plumbing and the contract assembly, so
// signature bugs and shape bugs surface instantly and offline. A dry run reports
// the PLAN (what it would do) and is marked dry_run:true in the result.
// ---------------------------------------------------------------------------
let DRY_RUN = false;

// Stub responses keyed by the role passed to runAgent — each matches the schema
// the real agent would return, so downstream stages get well-typed data and the
// control flow is identical to a live run.
function stubFor(opts) {
  const role = (opts && opts.role) || "agent";
  switch (role) {
    case "worker":
      return { isolation_confirmed: true, deps_fetched: true, compiled: true, committed: true,
        branch: "(dry-run)", commit: "0000000(dry-run)", files_changed: ["(dry-run)"],
        produced_contract: "(dry-run) produced contract", known_limitations: [], self_report: "dry-run stub" };
    case "reviewer":
      return { lens: "C", refuted: true, findings: [] }; // clean panel → no fixes, fast path
    case "fixer":
      return { finding_id: "(dry-run)", fixed: true, files_changed: [], commit: "0000000(dry-run)", note: "dry-run stub" };
    case "advocate": return { ok: true };
    case "critic": return { ok: true };
    case "judge": return { rulings: [] };
    case "verifier":
      return { verdict: "PASS", rigor: "read_only", reproduced: true,
        evidence: "(dry-run) no real verification performed", ref: "(dry-run)", criteria: [] };
    default:
      return { ok: true, dry_run: true };
  }
}

// Single choke point for every model call in this file. Honors DRY_RUN and the
// AGENT_CAP concurrency governor.
async function runAgent(prompt, opts) {
  if (DRY_RUN) return stubFor(opts);
  await _acquire();
  try {
    return await agent(prompt, opts);
  } finally {
    _release();
  }
}

// ---------------------------------------------------------------------------
// JSON schemas. agent() validates its return against these, so each stage hands
// the next stage typed structured data instead of free prose.
// ---------------------------------------------------------------------------

const workSchema = {
  type: "object",
  additionalProperties: false,
  required: [
    "isolation_confirmed",
    "deps_fetched",
    "compiled",
    "committed",
    "branch",
    "commit",
    "files_changed",
    "produced_contract",
    "self_report",
  ],
  properties: {
    isolation_confirmed: { type: "boolean", description: "git worktree list / pwd confirms a fresh isolated worktree" },
    deps_fetched: { type: "boolean", description: "mix deps.get ran successfully BEFORE any compile/test" },
    compiled: { type: "boolean", description: "mix compile --warnings-as-errors is green" },
    committed: { type: "boolean" },
    branch: { type: "string", description: "must equal fleet/<run-id>/task/<N>-<slug>" },
    commit: { type: "string", description: "HEAD sha of the named branch after the last commit" },
    files_changed: { type: "array", items: { type: "string" } },
    produced_contract: {
      type: "string",
      description: "the checkpoint/contract downstream tasks consume (API, schema, module, component); '' if none",
    },
    known_limitations: { type: "array", items: { type: "string" }, default: [] },
    self_report: { type: "string", description: "worker's own summary; treated as a CLAIM, not proof" },
  },
};

// C4 LensFinding (per-lens raw record). `refuted` (NOT `found`): refuted=true
// means the lens actively looked and found nothing in scope; refuted=false means
// it raised >=1 finding. Each raw finding carries the single `lens` provenance,
// `severity`/`confidence` enums, and `suggested_fix`. Disposition is NOT
// self-reported by the lens; it is proposed by policy and confirmed by judgment
// after dedupe (C8).
const lensRecordSchema = {
  type: "object",
  additionalProperties: false,
  required: ["lens", "refuted", "findings"],
  properties: {
    lens: { type: "string" },
    refuted: {
      type: "boolean",
      description: "true = this lens looked and actively found nothing in scope; false = it raised >=1 finding",
    },
    findings: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["severity", "confidence", "file", "line", "finding", "suggested_fix", "lens"],
        properties: {
          severity: { type: "string", enum: ["blocking", "major", "minor", "nit"] },
          confidence: { type: "string", enum: ["high", "medium", "low"] },
          file: { type: "string" },
          line: { type: "integer" },
          finding: { type: "string" },
          suggested_fix: { type: "string" },
          lens: { type: "string", description: "the single lens that raised it (provenance)" },
        },
      },
    },
  },
};

const fixSchema = {
  type: "object",
  additionalProperties: false,
  required: ["finding_id", "fixed", "files_changed", "commit", "note"],
  properties: {
    finding_id: { type: "string" },
    fixed: { type: "boolean" },
    files_changed: { type: "array", items: { type: "string" } },
    commit: { type: "string", description: "sha after the minimal fix commit on the task branch, or '' if unfixed" },
    note: { type: "string" },
  },
};

// C7 Judge ruling schema. The Judge emits ACCEPT/FIX_LATER/DEFER per contested
// finding (matching the disposition vocabulary in C4/C8), and this becomes the
// authoritative disposition for those findings.
const acjSchema = {
  type: "object",
  additionalProperties: false,
  required: ["rulings"],
  properties: {
    rulings: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["id", "ruling", "disposition", "rationale"],
        properties: {
          id: { type: "string" },
          ruling: { type: "string", enum: ["VALID", "INVALID", "NEEDS_EVIDENCE"] },
          disposition: { type: "string", enum: ["ACCEPT", "FIX_LATER", "DEFER"] },
          rationale: { type: "string" },
        },
      },
    },
  },
};

const verifySchema = {
  type: "object",
  additionalProperties: false,
  required: ["verdict", "rigor", "reproduced", "evidence", "ref", "criteria"],
  properties: {
    verdict: { type: "string", enum: ["PASS", "FAIL"] },
    rigor: { type: "string", enum: ["read_only", "snapshot", "browser_flow", "browser_flow_plus_arbiter"] },
    reproduced: { type: "boolean", description: "true = the verifier independently re-ran and observed the result" },
    evidence: {
      type: "string",
      description: "concrete observed evidence (real test output, what the browser showed) — NOT the worker's summary",
    },
    ref: { type: "string", description: "the exact branch-or-sha the verifier checked out (C1 verification.ref)" },
    criteria: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["criterion", "met"],
        properties: {
          criterion: { type: "string" },
          met: { type: "boolean" },
          observed: { type: "string", default: "" },
        },
      },
    },
    design_audit: {
      type: "object",
      additionalProperties: false,
      required: ["verdict", "violations"],
      properties: {
        verdict: { type: "string", enum: ["PASS", "FAIL", "N/A"] },
        violations: { type: "array", items: { type: "string" } },
      },
      default: { verdict: "N/A", violations: [] },
    },
  },
};

// ---------------------------------------------------------------------------
// Deterministic helpers. No clock, no randomness. All identity is derived from
// the wave payload passed to runWave(wave).
// ---------------------------------------------------------------------------

function branchName(wave, task) {
  // Prefer the skill-minted branch; fall back to the deterministic derivation.
  return task.branch || `fleet/${wave.run_id}/task/${taskId(task)}-${task.slug}`;
}

function worktreeName(wave, task) {
  return task.workspace_name || `fleet-${wave.run_id}-task-${taskId(task)}-${task.slug}`;
}

function taskId(task) {
  // C1: TaskResult.task_id matches the DAG node id. The payload may carry it as
  // `id` (RunTaskFleet 1a) or `task_id`; normalize to a stable string.
  return String(task.task_id != null ? task.task_id : task.id);
}

// Isolation mechanism (ADR 0003 — verified live; the earlier workspace:{mode}
// option is INERT and was removed).
//
//   * WRITE stages (work, fix, rescue): pass the REAL workflow-level flag
//     `isolation: "worktree"`. The runtime gives the agent its own fresh git
//     worktree. The engine auto-NAMES the branch, so the brief must then
//     `git checkout -b <named branch>` to land on fleet/<run-id>/task/<N>-<slug>
//     (the name wave integration merges by) before committing.
//   * READ stages (review, verify): NO isolation flag. A second isolation
//     worktree would be a DIFFERENT empty tree, not the worker's. Instead the
//     brief reads the COMMITTED branch tip from the shared git object store
//     (`git show <branch>:<path>`), which is visible regardless of the agent's
//     cwd because the worker committed to a branch in the same repo.
//
// Isolation worktrees PERSIST once they hold a commit; the SKILL removes them at
// wave integration/teardown (`git worktree remove --force`).
const WRITE_OPTS = { isolation: "worktree" };

function levelOf(task) {
  const l = (task.level || "L2").toUpperCase();
  return LENS_SETS[l] ? l : "L2";
}

function reReviewCap(task) {
  // The skill may pin rereview_cap in the payload (1a); fall back to the level.
  if (typeof task.rereview_cap === "number") return task.rereview_cap;
  return RE_REVIEW_CAP[levelOf(task)];
}

// Deterministic finding id from its coordinates — no counters that depend on
// evaluation order, so resume reproduces the same ids.
function findingId(task, f) {
  return `${taskId(task)}:${f.file}:${f.line}:${slug(f.finding)}`;
}

function slug(text) {
  return String(text)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
}

function sev(s) {
  return { nit: 1, minor: 2, major: 3, blocking: 4 }[s] || 0;
}

// Dedupe across lenses by (file, line, normalized finding); keep provenance so a
// multi-lens hit reads as higher confidence. A lens with refuted=true contributes
// nothing. Reads `refuted` (C4). Scalar `lens` pre-merge becomes array `lenses`.
function dedupeFindings(task, lensRecords) {
  const byKey = new Map();
  for (const lr of lensRecords) {
    if (!lr || lr.refuted) continue; // refuted = looked, nothing in scope
    for (const f of lr.findings || []) {
      const key = `${f.file}::${f.line}::${slug(f.finding)}`;
      if (byKey.has(key)) {
        const existing = byKey.get(key);
        if (!existing.lenses.includes(f.lens || lr.lens)) existing.lenses.push(f.lens || lr.lens);
        existing.confidence = existing.lenses.length > 1 ? "high" : existing.confidence;
        if (sev(f.severity) > sev(existing.severity)) existing.severity = f.severity;
      } else {
        byKey.set(key, {
          id: findingId(task, f),
          severity: f.severity,
          confidence: f.confidence,
          file: f.file,
          line: f.line,
          finding: f.finding,
          suggested_fix: f.suggested_fix,
          lens: f.lens || lr.lens,
          lenses: [f.lens || lr.lens],
        });
      }
    }
  }
  return Array.from(byKey.values());
}

// C8 disposition: POLICY PROPOSES. A pure function maps (severity, confidence)
// to a default disposition, so the common case is reproducible and resume-safe.
// This is only a PROPOSAL — judgment (single-lens lead) or the L4 Judge confirms
// or overrides it via resolveDisposition().
function proposeDisposition(f) {
  const multi = (f.lenses || []).length > 1 || f.confidence === "high";
  if (sev(f.severity) >= 3 && multi) return "ACCEPT"; // blocking/major + corroborated
  if (sev(f.severity) >= 3) return "ACCEPT"; // lone high-severity lead — judgment may demote
  if (sev(f.severity) === 2) return "FIX_LATER"; // medium/major default
  return "DEFER"; // minor/nit or out-of-scope
}

// C8 JUDGMENT CONFIRMS. The Judge's ruling (L4, when present) is authoritative
// for that finding; otherwise the policy proposal stands. The returned value is
// the authoritative `disposition` the fix/triage loop reads.
function resolveDisposition(f) {
  if (f.judge_disposition === "ACCEPT" || f.judge_disposition === "FIX_LATER" || f.judge_disposition === "DEFER") {
    return f.judge_disposition;
  }
  return proposeDisposition(f);
}

function lensBriefsForTask(task) {
  // Prefer the skill-sized lens list (1a review_lenses); fall back to the level set.
  const base = Array.isArray(task.review_lenses) && task.review_lenses.length
    ? task.review_lenses.slice()
    : LENS_SETS[levelOf(task)].slice();
  if (task.surface_type === "ui" || task.design === true) {
    if (!base.includes("D")) base.push("D"); // D takes a slot regardless of level
  }
  return base;
}

function effortFor(level) {
  return { L1: "medium", L2: "high", L3: "high", L4: "max" }[level] || "high";
}

// C3 wave-level techdebt entry in the ADR-pinned shape:
//   { task_id, branch, file, line, finding, lenses[], disposition, reason }
// `lenses` is ALWAYS an array; `reason` (never why_nonblocking).
function techdebtEntry(wave, task, f, reason) {
  return {
    task_id: taskId(task),
    branch: branchName(wave, task),
    file: f.file,
    line: f.line,
    finding: f.finding,
    lenses: (f.lenses && f.lenses.length ? f.lenses : [f.lens]).filter(Boolean),
    disposition: f.disposition, // FIX_LATER | DEFER — ACCEPT items are fixed, never debt
    reason,
  };
}

// ---------------------------------------------------------------------------
// Phase 1 — Work. One isolation-worktree agent per task. The brief hard-codes
// the two PROVEN POC facts so no worker re-derives them:
//   (1) a fresh engine worktree has NO fetched deps; the FIRST build action must
//       be `mix deps.get`, BEFORE any `mix compile` / `mix test`.
//   (2) commit to the NAMED branch fleet/<run-id>/task/<N>-<slug> so wave
//       integration can address and merge it; leave deps/_build/mix.lock unstaged.
// ---------------------------------------------------------------------------

async function workStage(wave, task) {
  const branch = branchName(wave, task);
  const worktree = worktreeName(wave, task);
  const level = levelOf(task);
  const useUltrathink = level !== "L1";
  const ctx = task.dag_context || {};

  const brief = [
    `You are the WORKER for task ${taskId(task)} (${task.slug}). ${useUltrathink ? "ultrathink. " : ""}` +
      `Run at ${task.effort || effortFor(level)} effort.`,
    "",
    "ISOLATION (verified facts — do not re-derive):",
    "- You are in a FRESH isolated git worktree the runtime created, but on an",
    "  ENGINE-AUTO-NAMED branch. FIRST, switch to the NAMED branch wave integration",
    `  will merge: \`git checkout -b ${branch}\` (cut from ${wave.base_branch}; it is your worktree's base).`,
    `  All your commits must land on ${branch}. Confirm with \`git rev-parse --abbrev-ref HEAD\` == ${branch}.`,
    "- A fresh worktree has NO fetched deps. Your FIRST build action MUST be `mix deps.get`.",
    "  Running `mix compile` or `mix test` before `mix deps.get` fails with",
    '  "Unchecked dependencies, run mix deps.get". Always: mix deps.get -> mix compile --warnings-as-errors -> mix test.',
    `- Commit your work to ${branch} (commit frequently). Do NOT detach HEAD.`,
    "- Review and verify read the COMMITTED branch tip via `git show`, not your scratch tree.",
    "  Uncommitted work is invisible to them — commit everything that matters.",
    "- deps/, _build/, and mix.lock are gitignored — leave them UNSTAGED so wave integration merges stay clean.",
    "",
    "TASK GOAL:",
    task.goal,
    "",
    "ACCEPTANCE CRITERIA (the independent verifier will test these — make them true and observable):",
    ...(task.acceptance_criteria || []).map((c) => `- ${c}`),
    "",
    "DAG CONTEXT:",
    `- Satisfied blocking dependencies: ${(ctx.blocking_satisfied || []).join(", ") || "none"}.`,
    `- Soft edges / seam obligations this wave: ${(ctx.soft_edges || []).join(", ") || "none"}.`,
    `- Produced checkpoint expected: ${ctx.produces || "(none)"}.`,
    `- Downstream tasks waiting on your checkpoint: ${(ctx.downstream_waiting || []).join(", ") || "none"}.`,
    "",
    "RULES:",
    "- Do NOT ask the user questions. Resolve ambiguity by investigating the codebase, pick the best-fit",
    "  trade-off, and document the assumption in your commit message.",
    "- Public fns return {:ok, _} | {:error, _}; Event data uses string keys (repo invariant).",
    "",
    "RETURN the work schema: isolation_confirmed, deps_fetched, compiled, committed, branch, commit,",
    "files_changed, produced_contract, known_limitations, self_report. self_report is a CLAIM — an",
    "independent verifier will check it later, so report honestly.",
  ].join("\n");

  const work = await runAgent(brief, {
    ...WRITE_OPTS, // real isolation:"worktree" (verified)
    role: "worker",
    effort: task.effort || effortFor(level),
    schema: workSchema,
  });

  return { task, branch, worktree, level, work };
}

// ---------------------------------------------------------------------------
// Phase 2 — Adversarial Review. Fan out one parallel Claude subagent per lens.
// Each lens is a DISTINCT skeptical brief told to REFUTE the work; independence
// is the diversity of lenses, not a second model. Each lens reads the COMMITTED
// branch tip from the shared git object store (`git show <branch>:<path>` /
// `git diff <base>...<branch>`) — no isolation flag (a second isolation worktree
// would be a different empty tree). It inspects what the gates will merge (and
// later, the committed fixes). Dedupe with provenance.
// ---------------------------------------------------------------------------

async function reviewStage(wave, prev) {
  const { task, branch, level } = prev;
  const lenses = lensBriefsForTask(task);

  // parallel() takes an ARRAY OF THUNKS (verified): parallel(items.map(x => () => ...)).
  const lensRecords = await parallel(
    lenses.map((lens) => () => {
      const brief = [
        `LENS = ${lens}. You are an ADVERSARIAL reviewer of branch ${branch} (task ${taskId(task)}, level ${level}).`,
        "Assume the implementation is WRONG until the code proves otherwise. Be brutally honest; no pleasantries.",
        `Read the COMMITTED tip of ${branch} from git (you are NOT auto-checked-out to it): inspect`,
        `\`git diff ${wave.base_branch}...${branch}\` and \`git show ${branch}:<file>\` for any file you need.`,
        `Review that diff THROUGH THIS LENS ONLY: ${LENS_FOCUS[lens]}.`,
        "If you need to build/run, check out the branch into a scratch worktree and run `mix deps.get` first",
        "(a fresh checkout is deps-bare). Do NOT trust the worker's summary; read the actual committed diff.",
        "Acceptance criteria for context:",
        ...(task.acceptance_criteria || []).map((c) => `- ${c}`),
        "",
        "Every real issue = { severity (blocking|major|minor|nit), confidence (high|medium|low), file, line,",
        `finding, suggested_fix, lens: "${lens}" }. If your lens finds nothing in scope, return refuted=true with`,
        "an empty findings array. If you raise any finding, return refuted=false. Do not invent issues outside",
        "your lens, and do not soften real ones.",
      ].join("\n");

      return runAgent(brief, { role: "reviewer", schema: lensRecordSchema });
    })
  );

  // L4: an Advocate-Critic-Judge trio over contested/high-severity findings (C7).
  // Three Claude subagents. ACJ counts inside the re-review cap; its Judge rulings
  // become the authoritative disposition for those findings (C8).
  let merged = dedupeFindings(task, lensRecords);
  if (level === "L4") {
    merged = await acjDebate(wave, task, merged);
  }

  return { ...prev, lenses, findings: merged, round: 1 };
}

// C7 Advocate-Critic-Judge: three distinct Claude subagents. Advocate argues the
// finding is refuted (correct), Critic argues it is real (broken), Judge rules
// each contested finding VALID/INVALID/NEEDS_EVIDENCE and sets the disposition
// (ACCEPT/FIX_LATER/DEFER), which resolveDisposition() honors (C8).
async function acjDebate(wave, task, findings) {
  const contested = findings.filter((f) => sev(f.severity) >= 3);
  if (contested.length === 0) return findings;

  const branch = branchName(wave, task);
  const payload = JSON.stringify(
    contested.map((f) => ({ id: f.id, severity: f.severity, file: f.file, line: f.line, finding: f.finding })),
    null,
    2
  );

  // 1. Advocate — argue the implementation is correct, citing code/tests.
  const advocate = await runAgent(
    [
      `You are the ADVOCATE in an Advocate-Critic-Judge debate on branch ${branch} (task ${taskId(task)}, L4).`,
      "For each contested finding, argue the implementation is actually CORRECT, citing concrete code and tests",
      "you read in the shared checkout. Be specific; cite file:line. Return prose per finding id.",
      "Contested findings:",
      payload,
    ].join("\n"),
    { role: "advocate", schema: { type: "object", additionalProperties: true, required: [], properties: {} } }
  );

  // 2. Critic — argue it is wrong, surfacing runtime and edge-case failures.
  const critic = await runAgent(
    [
      `You are the CRITIC in an Advocate-Critic-Judge debate on branch ${branch} (task ${taskId(task)}, L4).`,
      "For each contested finding, argue the implementation is WRONG: surface the concrete runtime path or",
      "edge case that fails, citing file:line. Rebut the advocate where you can. Return prose per finding id.",
      "Advocate's case:",
      JSON.stringify(advocate),
      "Contested findings:",
      payload,
    ].join("\n"),
    { role: "critic", schema: { type: "object", additionalProperties: true, required: [], properties: {} } }
  );

  // 3. Judge — rule VALID/INVALID/NEEDS_EVIDENCE and SET the disposition.
  const ruling = await runAgent(
    [
      `You are the JUDGE in an Advocate-Critic-Judge debate on branch ${branch} (task ${taskId(task)}, L4).`,
      "Weigh the advocate (code is correct) against the critic (it fails). For EACH contested finding rule it",
      "VALID / INVALID / NEEDS_EVIDENCE and SET its disposition ACCEPT / FIX_LATER / DEFER. Your disposition is",
      "AUTHORITATIVE and replaces the policy proposal for these findings. You may read the shared checkout to",
      "settle NEEDS_EVIDENCE.",
      "Advocate's case:",
      JSON.stringify(advocate),
      "Critic's case:",
      JSON.stringify(critic),
      "Contested findings:",
      payload,
    ].join("\n"),
    { role: "judge", schema: acjSchema }
  );

  const byId = new Map(ruling.rulings.map((r) => [r.id, r]));
  return findings.map((f) => {
    const r = byId.get(f.id);
    if (!r) return f;
    return { ...f, judge: r.ruling, judge_disposition: r.disposition };
  });
}

// ---------------------------------------------------------------------------
// Phase 3 + 4 — Disposition + Fix, then capped Re-review. Disposition is policy
// proposal, confirmed/overridden by judgment or the L4 Judge (C8). One fix
// subagent per ACCEPT finding, in parallel (a barrier), in the ISOLATION
// worktree, committing to the branch (C5/C6). The loop runs AT MOST `cap` review
// rounds (round < cap) — exactly N, never N+1 (C9). At the cap with ACCEPT still
// open, escalate to ONE higher-effort rescue subagent, re-review once; still red
// -> needs_orchestrator so the SKILL arbitrates between waves.
// ---------------------------------------------------------------------------

async function fixStage(wave, prev) {
  const { task, branch, level } = prev;
  const cap = reReviewCap(task);

  let findings = prev.findings;
  let round = prev.round || 1;
  let rescued = false;
  const fixLog = [];
  const techdebt = [];

  // De-dupe techdebt across rounds by finding id (same FIX_LATER/DEFER may recur).
  const debtSeen = new Set();
  function recordDebt(dispositioned) {
    for (const f of dispositioned.filter((d) => d.disposition === "FIX_LATER" || d.disposition === "DEFER")) {
      if (debtSeen.has(f.id)) continue;
      debtSeen.add(f.id);
      const reason = f.disposition === "FIX_LATER" ? "real but non-blocking" : "out of scope for this task";
      techdebt.push(techdebtEntry(wave, task, f, reason));
    }
  }

  while (true) {
    const dispositioned = findings.map((f) => ({ ...f, disposition: resolveDisposition(f) }));
    const accepts = dispositioned.filter((f) => f.disposition === "ACCEPT");
    recordDebt(dispositioned);

    if (accepts.length === 0) {
      return { ...prev, findings: dispositioned, round, rescued, fixLog, techdebt, fix_status: "clean" };
    }

    // Cap reached (we've already run `cap` review rounds): one rescue, one re-review.
    if (round >= cap) {
      const rescueResult = await rescue(wave, task, accepts);
      fixLog.push(...rescueResult.fixLog);
      rescued = true;

      const reReviewed = await reReview(wave, task, level, round + 1);
      const reDisp = reReviewed.map((f) => ({ ...f, disposition: resolveDisposition(f) }));
      recordDebt(reDisp);
      const stillAccept = reDisp.filter((f) => f.disposition === "ACCEPT");

      if (stillAccept.length === 0) {
        return { ...prev, findings: reDisp, round: round + 1, rescued, fixLog, techdebt, fix_status: "clean_after_rescue" };
      }
      // Still red: hand the decision to the skill (re-scope / downgrade / hold).
      return {
        ...prev,
        findings: reDisp,
        round: round + 1,
        rescued,
        fixLog,
        techdebt,
        fix_status: "needs_orchestrator",
        unresolved: stillAccept,
      };
    }

    // Fix subagents run SEQUENTIALLY, not in parallel: each gets its own fresh
    // isolation worktree, but they all target the SAME named branch, and git
    // forbids checking out one branch in two worktrees at once (parallel fixers
    // would collide or diverge). One finding at a time; each commits to the
    // branch before the next starts, so the branch advances linearly. Tasks
    // across the wave still pipeline in parallel — only fixes WITHIN a task
    // serialize, and ACCEPT findings are usually few.
    for (const f of accepts) {
      const fix = await runAgent(
        [
          `You are a FIX subagent for branch ${branch} (task ${taskId(task)}). You start in a FRESH isolated`,
          `worktree on an auto-named branch — FIRST check out the existing committed branch: \`git checkout ${branch}\``,
          `(it already holds the worker's and any prior fixers' commits). Make the MINIMAL correct change for`,
          `exactly this finding, then verify locally (mix deps.get if needed -> mix compile -> mix test).`,
          `COMMIT to ${branch} — an uncommitted edit is invisible to review/verify (they read the committed tip).`,
          "Return the fix schema.",
          "Finding:",
          JSON.stringify(
            { id: f.id, file: f.file, line: f.line, finding: f.finding, suggested_fix: f.suggested_fix },
            null,
            2
          ),
        ].join("\n"),
        { ...WRITE_OPTS, role: "fixer", schema: fixSchema }
      );
      fixLog.push(fix);
    }

    // Phase 4: re-run the panel on the patched COMMITTED tree (shared ref).
    findings = await reReview(wave, task, level, round + 1);
    round += 1;
  }
}

async function reReview(wave, task, level, round) {
  const branch = branchName(wave, task);
  const lenses = lensBriefsForTask(task);

  const lensRecords = await parallel(
    lenses.map((lens) => () =>
      runAgent(
        [
          `LENS = ${lens}. RE-REVIEW (round ${round}) of branch ${branch} (task ${taskId(task)}).`,
          `Assume the fixes are insufficient until proven otherwise. THIS LENS ONLY: ${LENS_FOCUS[lens]}.`,
          "You read a fresh SHARED checkout of the committed branch tip (deps-bare — run `mix deps.get` first).",
          "Only report findings still present in the patched tree. Same schema as before:",
          `refuted=true with empty findings if clean, refuted=false with findings (tagged lens: "${lens}") otherwise.`,
        ].join("\n"),
        { role: "reviewer", schema: lensRecordSchema }
      )
    )
  );

  let merged = dedupeFindings(task, lensRecords);
  if (level === "L4") merged = await acjDebate(wave, task, merged); // ACJ stays inside the cap
  return merged;
}

async function rescue(wave, task, accepts) {
  const branch = branchName(wave, task);
  const fix = await runAgent(
    [
      `You are a RESCUE subagent for branch ${branch} (task ${taskId(task)}). Run at MAX effort, ultrathink.`,
      `You start in a fresh isolated worktree on an auto-named branch — FIRST \`git checkout ${branch}\` (it holds`,
      "all prior commits). The normal fix loop hit its re-review cap with these ACCEPT findings still open.",
      "Take a higher-effort pass: investigate root cause, fix all of them correctly, run the full build",
      `(mix deps.get -> mix compile --warnings-as-errors -> mix test), COMMIT to ${branch}.`,
      "Return the fix schema for the most significant change you made.",
      JSON.stringify(accepts.map((f) => ({ id: f.id, file: f.file, line: f.line, finding: f.finding })), null, 2),
    ].join("\n"),
    { role: "rescue", effort: "max", ...WRITE_OPTS, schema: fixSchema }
  );
  return { fixLog: [fix] };
}

// ---------------------------------------------------------------------------
// Phase 5 — Verify. An INDEPENDENT verifier subagent reading the COMMITTED
// branch tip from git (`git show <branch>:<path>` / checkout into a scratch
// worktree) — so it can never verify a tree without the committed fixes. It must
// reproduce evidence (run the tests,
// drive the app) — it may NOT accept the worker's self-report as proof. Rigor is
// the level's calibrated tier. UI/design tasks add a design audit; a design FAIL
// is a verifier FAIL. Independent verification is what gates a task to
// status "checkpoint_ready".
// ---------------------------------------------------------------------------

async function verifyStage(wave, prev) {
  const { task, branch, level } = prev;
  const rigor = VERIFY_RIGOR[level];
  const isUi = task.surface_type === "ui" || task.design === true;

  const verify = await runAgent(
    [
      `You are an INDEPENDENT verifier for task ${taskId(task)} on branch ${branch}. Rigor: ${rigor}.`,
      `You are NOT auto-checked-out to the branch. Get the COMMITTED tip yourself: check out ${branch} into a`,
      `scratch worktree (\`git worktree add ../verify-${taskId(task)} ${branch}\`) — it contains every committed`,
      "fix. It is a fresh deps-bare tree: run `mix deps.get` FIRST.",
      "Do NOT trust the worker's self-report. Reproduce evidence yourself:",
      "1. In that checkout run `mix deps.get` then `mix test` and read the REAL output (no swallowed errors).",
      rigor === "read_only"
        ? "2. Confirm the claimed files exist and tests pass from the actual output."
        : "2. Drive the affected behavior (browser snapshot for L2, full flow for L3, full flow + your own diff read for L4) and confirm each acceptance criterion.",
      isUi
        ? "3. DESIGN AUDIT: check the rendered result against the project design SOP (surface type, canonical-component reuse, exact-layout match, superseded code removed). A design FAIL is a verifier FAIL."
        : "",
      "Acceptance criteria to test:",
      ...(task.acceptance_criteria || []).map((c) => `- ${c}`),
      "",
      "RETURN the verify schema: verdict, rigor, reproduced (true iff you independently re-ran), evidence",
      "(concrete observed output, NOT a restatement of the worker's claim), ref (the exact branch/sha you",
      "checked out), criteria.",
    ]
      .filter(Boolean)
      .join("\n"),
    { role: "verifier", schema: verifySchema }
  );

  return { ...prev, rigor, verify };
}

// ---------------------------------------------------------------------------
// validateWave — ADR 0005 actionable input validation. Returns null when valid,
// or a structured error whose message states the FIX, with a branchable `kind`.
// ---------------------------------------------------------------------------
function validateWave(wave) {
  if (!wave || typeof wave !== "object") {
    return { kind: "invalid_args", message: "runWave(wave) requires a wave object. Pass the ready-set payload (see describe().input).", details: { received: typeof wave } };
  }
  const missing = [];
  if (!wave.run_id) missing.push("run_id (string, e.g. \"20260603-143000\")");
  if (!wave.base_branch) missing.push("base_branch (string, the branch tasks are cut from)");
  if (!Array.isArray(wave.tasks) || wave.tasks.length === 0) missing.push("tasks (non-empty array of task nodes)");
  if (missing.length) {
    return {
      kind: "invalid_args",
      message: `runWave is missing required wave fields: ${missing.join("; ")}. ` +
        "The SKILL builds this payload from the approved DAG (RunTaskFleet 1a); it is never minted inside a workflow.",
      details: { run_id: wave.run_id || null, base_branch: wave.base_branch || null, task_count: Array.isArray(wave.tasks) ? wave.tasks.length : 0 },
    };
  }
  // Per-task: each needs an id and slug so branch/worktree names are derivable.
  const badTasks = [];
  wave.tasks.forEach((t, i) => {
    const id = t && (t.task_id != null ? t.task_id : t.id);
    if (id == null || !t.slug) badTasks.push({ index: i, has_id: id != null, has_slug: !!(t && t.slug) });
  });
  if (badTasks.length) {
    return {
      kind: "invalid_args",
      message: "Every task needs an id (task_id or id) and a slug — they derive the branch fleet/<run-id>/task/<id>-<slug>. " +
        "Fix the offending task nodes in the DAG before calling runWave.",
      details: { offending_tasks: badTasks },
    };
  }
  return null;
}

// ---------------------------------------------------------------------------
// describe — ADR 0005 self-describing. Returns the input contract and the
// wave-result shape as DATA, so the skill (or a human) can introspect what this
// script expects and returns without reading the source. This is the workflow
// equivalent of `--help`.
// ---------------------------------------------------------------------------
async function describe() {
  return {
    ok: true,
    name: "runWave",
    summary: meta.description,
    contract: "ADR 0002 C1-C9 (binding); this script is the executable source of truth.",
    input: {
      shape: "runWave(wave)",
      wave: {
        run_id: "string (skill-minted; scripts cannot read the clock)",
        base_branch: "string (branch the wave's tasks are cut from)",
        wave: "number (wave index, optional, echoed back)",
        dry_run: "boolean (optional; true = stub all agents, no model/worktree/mix; returns the plan)",
        tasks: [{
          task_id: "string|number (or `id`)", slug: "string",
          goal: "string", level: "L1|L2|L3|L4 (default L2)",
          acceptance_criteria: "string[]", review_lenses: "string[] (optional; else level set)",
          rereview_cap: "number (optional; else level cap)", effort: "string (optional)",
          surface_type: "\"ui\" (optional; adds lens D + design audit)",
          branch: "string (optional; else derived)", workspace_name: "string (optional; else derived)",
          dag_context: "{ blocking_satisfied[], soft_edges[], produces, downstream_waiting[] }",
        }],
      },
    },
    output: {
      success: "{ ok:true, dry_run, run_id, wave, tasks: TaskResult[], techdebt: TechdebtEntry[] }",
      error: "{ ok:false, dry_run, error:{ kind, message, details } }  // kind ∈ invalid_args | stage_failed",
      TaskResult: "{ task_id, slug, branch, commit|null, status, produced_contract, known_limitations[], review{verdict,rounds,rescued,findings}, verification{reproduced,evidence,ref} }",
      status_enum: ["checkpoint_ready", "held (set by skill, not script)", "needs_orchestrator"],
      TechdebtEntry: "{ task_id, branch, file, line, finding, lenses[], disposition(FIX_LATER|DEFER), reason }",
    },
    levels: { lens_sets: LENS_SETS, rereview_cap: RE_REVIEW_CAP, verify_rigor: VERIFY_RIGOR },
    constraints: [
      "Runs to completion; NO mid-run user input (the DAG-approval gate lives in the skill, between waves).",
      "No filesystem, no clock/randomness; returns pure data. The skill writes fleet.json and stamps time.",
      "Claude-only review (no Codex); independence is from diverse skeptical lens briefs.",
    ],
  };
}

// ---------------------------------------------------------------------------
// runWave — entry point. Reads the ready-set payload from its `wave` argument
// (RunTaskFleet 1a/1b), pipelines every task through work -> review -> fix ->
// verify, and assembles the wave-result per ADR 0002 C1-C3. Returns pure data;
// the skill stamps timestamps and writes .orchestrator/fleet.json. Pass
// wave.dry_run:true to walk the plan with stubbed agents (no side effects).
// ---------------------------------------------------------------------------

async function runWave(wave) {
  // ADR 0005: structured, actionable errors. Each message states the fix, and
  // `kind` is branchable by the skill (invalid_args | stage_failed).
  const err = validateWave(wave);
  if (err) return { ok: false, dry_run: !!(wave && wave.dry_run), error: err };

  // ADR 0005: dry-runnable. dry_run walks the full control flow with stubbed
  // agents — no model calls, no worktrees, no mix, no commits — and returns the
  // plan. It is the free offline harness for this script's own plumbing.
  DRY_RUN = wave.dry_run === true;

  // One item per task in the ready set; stages have no barrier between them, so a
  // fast task can reach verify while a slower sibling is still in work. The outer
  // concurrency is the skill-sized ready-set width (1a); the AGENT_CAP semaphore
  // bounds total live agents (including inner lens panels) at ~16 (C9).
  // pipeline(items, ...stages) — stages are functions, NO options object (verified).
  let results;
  try {
    results = await pipeline(
      wave.tasks,
      (task) => workStage(wave, task),
      (prev) => reviewStage(wave, prev),
      (prev) => fixStage(wave, prev),
      (prev) => verifyStage(wave, prev)
    );
  } catch (e) {
    DRY_RUN = false;
    return {
      ok: false,
      dry_run: wave.dry_run === true,
      run_id: wave.run_id,
      wave: wave.wave,
      error: {
        kind: "stage_failed",
        message: `A wave stage threw: ${String((e && e.message) || e)}. ` +
          "This is a bug in a stage or a model/runtime failure, not bad input. " +
          "Re-run with dry_run:true to isolate it from model/worktree effects.",
        details: { stack: e && e.stack ? String(e.stack).split("\n").slice(0, 4).join("\n") : null },
      },
    };
  } finally {
    DRY_RUN = false; // never leak the flag across invocations (resume-safety)
  }

  // C1: one TaskResult per task. C3: wave-level techdebt, flattened across tasks.
  const tasks = results.map((r) => toTaskResult(wave, r));
  const techdebt = results.flatMap((r) => r.techdebt || []);

  return {
    dry_run: wave.dry_run === true,
    ok: true,
    run_id: wave.run_id,
    wave: wave.wave,
    tasks,
    // C3: WAVE-LEVEL top-level techdebt array (ADR C1 names this field `techdebt`).
    techdebt,
  };
}

// C1 TaskResult — the exact, binding shape:
//   { task_id, slug, branch, commit, status, produced_contract, known_limitations,
//     review{verdict,rounds,rescued,findings}, verification{reproduced,evidence,ref} }
// C2 status ∈ { checkpoint_ready | held | needs_orchestrator }. There is NO
// `green` literal. checkpoint_ready means independent verification PASS, design
// PASS/N/A, and no remaining ACCEPT findings. Worker-says-done is never enough.
// `commit` is null iff status != "checkpoint_ready" (C1).
function toTaskResult(wave, r) {
  const { task, branch, work, verify, findings, fix_status, round, rescued } = r;
  const dispositioned = (findings || []).map((f) => ({ ...f, disposition: f.disposition || resolveDisposition(f) }));
  const accepts = dispositioned.filter((f) => f.disposition === "ACCEPT");

  const reviewClean = accepts.length === 0;
  const reviewVerdict = reviewClean ? "pass" : "fail"; // C1 review.verdict ∈ {pass, fail}
  const verifyVerdict = verify ? verify.verdict : "FAIL";
  const designVerdict = verify && verify.design_audit ? verify.design_audit.verdict : "N/A";

  // C2 status. The script emits only checkpoint_ready / needs_orchestrator; the
  // skill writes `held` into the ledger for dependents of a non-green upstream.
  let status;
  if (fix_status === "needs_orchestrator") {
    status = "needs_orchestrator";
  } else if (verifyVerdict === "PASS" && designVerdict !== "FAIL" && reviewClean) {
    status = "checkpoint_ready";
  } else {
    status = "needs_orchestrator"; // verify FAIL / design FAIL / ACCEPT remaining → skill arbitrates
  }

  return {
    task_id: taskId(task), // C1: canonical, NOT `id`
    slug: task.slug,
    branch,
    commit: status === "checkpoint_ready" && work ? work.commit : null, // C1: null iff not checkpoint_ready
    status, // C2
    produced_contract: work ? work.produced_contract : "", // C1: NOT `produced`
    known_limitations: (work && work.known_limitations) || [], // C1: NOT `limitations`
    review: {
      verdict: reviewVerdict, // pass | fail
      rounds: round || 1, // review rounds actually run
      rescued: !!rescued, // true iff rescue subagent was invoked
      findings: dispositioned.map((f) => ({
        // C4 LensFinding (post-merge carries lenses[] provenance; lens retained for the lead)
        refuted: false, // a surfaced finding is a non-refuted result
        severity: f.severity, // blocking | major | minor | nit
        file: f.file,
        line: f.line,
        finding: f.finding,
        suggested_fix: f.suggested_fix,
        lens: f.lens, // the single lens that raised it (provenance)
        lenses: f.lenses, // merged provenance array (multi-lens corroboration)
        confidence: f.confidence, // high | medium | low
        disposition: f.disposition, // C8: authoritative (policy proposed, judgment/ACJ confirmed)
        judge: f.judge || null, // L4 ACJ ruling, when present
      })),
    },
    verification: {
      // C1: independent re-run, NOT worker self-report
      reproduced: verify ? !!verify.reproduced : false,
      evidence: verify ? verify.evidence : "verifier did not run",
      ref: verify && verify.ref ? verify.ref : branch, // the exact ref the verifier checked out
    },
  };
}

// ---------------------------------------------------------------------------
// Self-executing entry (ADR 0003). The Workflow runtime sets a global `args`
// (the value the agent passes as Workflow({ scriptPath, args })) and EXECUTES
// this body — it does NOT call an exported function. So we dispatch on `args`:
//   * args.describe === true  -> return the self-description (queryable contract)
//   * otherwise               -> args IS the wave payload; run the wave.
// `args` may be undefined if the script is run with no input; treat that as a
// describe() call so a bare run is harmless and informative rather than an error.
// dry-run is selected by args.dry_run (read inside runWave).
// ---------------------------------------------------------------------------
let __args = typeof args !== "undefined" && args ? args : null;
// Some harness paths deliver args as a JSON-encoded string; accept both shapes.
if (typeof __args === "string") {
  try {
    __args = JSON.parse(__args);
  } catch (e) {
    __args = null;
  }
}
// No args, or an explicit describe request -> return the self-description (a bare
// run is harmless and informative). Otherwise __args IS the wave payload.
return !__args || __args.describe ? await describe() : await runWave(__args);
