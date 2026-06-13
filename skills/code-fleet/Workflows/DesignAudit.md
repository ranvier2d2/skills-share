# DesignAudit Workflow — enforce the design SOP on created UI

A **design-focused audit** that checks created/ported UI against the project's *already-established* design standard — the gap that a generic correctness review misses. Run it (a) as the design half of Phase 5 verification for any UI/design task, and (b) standalone to audit an existing branch/PR before it ships. The auditor **observes and judges; it does not fix** — it returns a PASS/FAIL + a per-rule violation list that feeds disposition (Phase 3) or a follow-up fix pass.

## Inputs the auditor must load first
1. **The project design SOP** — the enforceable standard + ranked sources (this repo: `ai_docs/design-sop.md`). If absent, the audit's first finding is "no codified SOP — cannot enforce; codify it."
2. **The canonical in-app design source** — the `/design` route and the component it renders (here `web/src/routes/DesignThemePage.tsx`): the real components/patterns and the **surface-type taxonomy** (Type 1 dotted work surface, Type 2 orchestration, Type 3 registry, Type 4 kanban).
3. **The layout contract** — the wireframe HTML anchor for the page(s) under audit.
4. **The running app** (a dev server) + **the diff** of what was built.

## The auditor sub-agent (spawn per UI task, or once per page for a standalone audit)
```
Agent(general-purpose, label="design-audit <page>"):
  "You are a DESIGN AUDITOR. Judge whether <page> complies with the project design SOP — do NOT trust the worker, and do NOT fix anything. Load, in order:
   1. The SOP: ai_docs/design-sop.md (ranked sources + surface-type taxonomy + the compliance checklist).
   2. The canonical design source: the /design route component (DesignThemePage.tsx) — note the components/patterns it already implements and the surface-type definitions.
   3. The wireframe anchor for this page in the v30 HTML.
   Then drive the running app with whatever browser tooling is available (a browser-automation skill/MCP: open <url>, snapshot, eval DOM) AND read the page's source/diff from the committed branch tip, and grade EVERY rule in the SOP compliance checklist. For each: PASS or FAIL with concrete evidence (DOM selector seen/absent, file:line, screenshot note). Pay special attention to:
     - SURFACE TYPE: is the page classified correctly, and for a Type-1 work surface is the main content actually inside the dashed outline (.subpage-workspace-dotted or its namespaced equivalent — verify the dashed border exists in the rendered DOM, not just intended)?
     - FORBIDDEN-IN-DOTTED: no approve-all / select-all / broad-approval controls inside a Type-1 dotted surface; single clear initiative; exception-not-approval model.
     - CANONICAL REUSE: does it REUSE the /design components/patterns (utility controls, focus/continuity modal, branch toggle) or did it REINVENT them? Reinvention of an existing canonical pattern is a FAIL.
     - EXACT LAYOUT: matches the wireframe structure, footer text, and copy; v30 SVG utility icons (no text glyphs); correct action-pair colors (steel review/edit, moss commit/request).
     - SUPERSEDED CODE REMOVED: grep the page for leftover old simplified markup, dead code, and window.alert stubs — any found = FAIL.
   Return a verdict: PASS (all rules pass) or FAIL, with a numbered violation list: {rule, severity, file:line or DOM evidence, what's wrong, the SOP reference}. Be concrete; this gates the task."
```

## Disposition of audit findings
- Audit findings flow through the normal **ACCEPT / FIX_LATER / DEFER** model (`references/review-verification.md`). A missing dotted outline, a reinvented-instead-of-reused canonical component, or leftover superseded code are typically **ACCEPT** (fix now). Minor copy/spacing deltas may be FIX_LATER.
- In the per-task pipeline: a design-audit FAIL == a Phase-5 FAIL → bounce to the worker, re-run Phases 3–4.
- Standalone (auditing an existing branch/PR): collect all pages' violations, then spawn one fix sub-agent per ACCEPT violation (or hand the list back as a remediation brief).

## Standalone usage (audit an existing PR before main)
1. Check out the branch; start a dev server (`PORT=<p> bun --hot web/index.html`).
2. Spawn one auditor per page (parallel), each returning its violation list.
3. Aggregate → disposition → either fix now (one Claude sub-agent per ACCEPT) or report the prioritized list as a remediation brief for the human to execute.

## Output
- Per-page PASS/FAIL + a prioritized, evidence-backed violation list keyed to SOP rules — the design equivalent of the review panel's findings, suitable for direct disposition.
