# Forward-Test Scenarios

Use these scenarios when testing whether `intent-html-renderer` still makes the right target, Shadcn, and validation decisions. Keep subagent prompts close to these user requests and avoid leaking expected implementation details.

## Scenario Matrix

| ID | User Request | Expected Target | Must Prove |
| --- | --- | --- | --- |
| decision-dashboard | "I need a UI that helps me decide which json-render components should be exposed to customers first, which ones are still internal-only, and what docs or demos are missing before launch." | Local Next/Shadcn route when available | Uses local Shadcn primitives, infers decision UI, validates route, no layout/component clarification request |
| settings-workflow | "I need a settings workflow UI for configuring json-render launch packaging: audience, docs completeness, demo readiness, risk tolerance, and final exposure lane." | Local Next/Shadcn route when available | Uses form/settings primitives such as `Field`, `FieldGroup`, `InputGroup`, `ToggleGroup`, `Select`/inputs where installed |
| prompt-workbench | "I need a prompt-to-UI workbench that lets me type a natural-language UI request, see the inferred intent, preview the JSON-render tree, and inspect validation issues before rendering." | Local Shadcn/json-render route or UI tree preview | Uses json-render context, validates saved UI tree when present, shows intent/tree/validation/preview surfaces |
| global-host-fallback | "I need a polished command workbench for choosing which support operations to automate first, but this repo has no frontend app." | Global Shadcn render host when no local UI dependencies exist | `detect_ui_target.py` recommends `global-shadcn-render-host`, host route uses real host UI components, host validator/type-check/browser proof run |
| partial-proof-closure | "Create an operations dashboard in a repo with no frontend app, then verify it visually even if Chrome headless writes screenshots but times out." | Global Shadcn render host when no local UI dependencies exist | Reports exact `proofState`; treats `partial_visual_evidence` as partial proof, inspects written screenshots when possible, and does not claim complete browser proof unless a clean rerun succeeds |
| portable-html | "Create a portable standalone HTML artifact I can send to a teammate that explains which json-render demos are launch-ready and which need work." | Standalone HTML even inside a Shadcn app repo | `detect_ui_target.py --intent` returns `standalone-html`, HTML validator passes, desktop/mobile visual proof attempted |
| preset-safeguard | "Make this project's Shadcn UI feel more like Luma or Nova before demos." | Approval-gated plan or route-local demo, not mutation | Does not run `shadcn apply`, `shadcn init --preset`, file-writing `shadcn add`, `--overwrite`, or global theme edits without approval |

## Pass Criteria

Every implementation scenario should report:

- Artifact path.
- Target decision and local evidence.
- Whether Shadcn CLI context succeeded or offline context fallback was used.
- Validation commands and results.
- Browser proof state, including whether screenshots were complete, partial, blocked, or manually inspected.
- Skill shortcomings encountered.

Every generated Shadcn route should pass:

```bash
python3 $SKILL_ROOT/scripts/validate_shadcn_route.py --cwd <repo> --route-file <route>
```

Every generated UI tree should pass:

```bash
python3 $SKILL_ROOT/scripts/validate_ui_tree.py <tree.json> --catalog <catalog.ts> --registry <registry.tsx>
```

Every standalone HTML artifact should pass:

```bash
python3 $SKILL_ROOT/scripts/validate_html_artifact.py <artifact.html> --strict
```

## Failure Signals

Treat these as actionable skill gaps:

- The agent asks the user to choose layout, components, or screens for an intent-only prompt.
- The agent creates standalone HTML when a local app target exists and no portable artifact was requested.
- The agent ignores an explicit portable/standalone HTML request.
- Shadcn CLI failure blocks progress instead of falling back to local context.
- Repo-wide Shadcn preset/theme mutation is performed without user approval.
- HTTP 200 or non-empty screenshot files are reported as complete visual proof without checking `proofState`, `captureState`, and screenshot quality.
- Validators pass but mobile/browser proof shows clipping or horizontal overflow.
- Generated Shadcn routes use raw tables, ad hoc badges/buttons/alerts, raw Tailwind colors, or invalid component composition without a waiver.

## Subagent Prompt Shape

Use prompts like:

```text
Forward-test the skill at /absolute/path/to/intent-html-renderer.
Scenario: Use $intent-html-renderer to satisfy this user request: "<scenario request>".
Infer the UI yourself. Do not ask for layout, components, or screens.
Use local repo context if helpful. Use a unique route/file name containing "<scenario id>".
Validate using the skill's relevant validators and project checks if feasible.
Final answer: summarize what you built, list changed file paths, commands run, and any skill shortcomings you encountered.
```

Do not pass expected target or hidden pass criteria unless the goal is specifically to audit target selection.
