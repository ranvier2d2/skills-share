# Pressure Tests

Use these when validating changes to this skill. The tests are designed to catch drift back to standalone HTML or generic UI.

## Ranvier Productization Prompt

Prompt:

```text
I need to understand which Ranvier projects are productizable, which product bundles are strongest, and what packaging work is needed before demos or sales.
```

Expected target in `$WORKSPACE_PATH`:

- Next/Shadcn route, not standalone HTML.
- Uses local `components/ui` primitives and repo import aliases.
- Shows a decision surface: ranked projects, bundle strength, packaging gaps, demo/sales readiness, recommended next actions.
- Validates with `validate_shadcn_route.py`, `pnpm type-check`, and browser proof.

Set `WORKSPACE_PATH` to a local Next/Shadcn workspace before running this pressure test.

Failure modes:

- Creates only an HTML file.
- Uses generic cards without local Shadcn imports.
- Presents a marketing page instead of a decision dashboard/report.

## Five YouTube Videos Prompt

Prompt:

```text
Create a UI for 5 youtube videos.
```

Expected target in a Shadcn app:

- Native route or json-render preview using local components.
- Five inspectable video items with realistic titles, metadata, thumbnails or styled thumbnail stand-ins, and visible actions.
- No clipped fifth item on desktop or mobile.

## Portable HTML Prompt

Prompt:

```text
Make a portable single-file HTML report for this analysis.
```

Expected target:

- Standalone HTML is correct because portability is explicit.
- Uses `assets/standalone-template.html`.
- Validates with `validate_html_artifact.py --strict`.

## Action-Command Prompt

Prompt:

```text
Convert my MP4 videos in /Projects/Videos to WebM, optimize for web, keep under 10MB.
```

Expected target:

- Action-command workflow.
- Unified command input, detected files/assumptions, clarification controls for missing settings, progress/logs, result summary, recoverable errors.
- Native app route when local app exists; standalone only without app context.

## No-App Workspace Prompt

Prompt:

```text
Build a small browser-viewable dashboard from this summary.
```

Expected target in a temporary folder with no app files:

- Standalone HTML.
- Strict HTML validation.
- Desktop and mobile browser proof when possible.
