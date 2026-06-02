# JSON Render Guidance

Use this for prompt-to-UI workbenches, JSON-driven UI previews, and natural-language action tools.

## Two Modes

- **Inspiration mode:** borrow the workflow pattern without depending on json-render. Use this when building ordinary dashboards, reports, or standalone artifacts.
- **Operational mode:** emit or validate actual json-render UI trees. Use this when the repo has `shadcnCatalog`, `shadcnRegistry`, `Renderer`, `JSONUIProvider`, or the user asks for JSON-driven rendering.

## Transferable Pattern

The useful pattern is the pipeline:

1. Accept a unified natural-language input.
2. Infer the likely task and artifact type.
3. Map the intent into a structured component plan.
4. Validate the plan.
5. Render visible UI.
6. Show useful feedback: suggestions, preview/code toggles, copy actions, status, and debug details.

## Operational json-render Pattern

When working inside a json-render repo:

- Use the local catalog prompt generator, for example `generateCatalogPrompt(shadcnCatalog)`, to constrain model output.
- Ensure emitted element `type` values exist in both the catalog and registry.
- Ensure elements with children use component types marked with `hasChildren: true` in the catalog when that metadata is available.
- Pass the registry into `Renderer` or `JSONUIProvider` according to the repo's existing pattern.
- Save private or sample UI trees only when useful for validation or tests.

Validate saved trees with:

```bash
python3 $SKILL_ROOT/scripts/validate_ui_tree.py tree.json \
  --catalog /path/to/shadcn-catalog.ts \
  --registry /path/to/shadcn-registry.tsx
```

## Private Component Plan

Sketch a private flat tree before writing complex UI:

```json
{
  "root": "workspace",
  "elements": {
    "workspace": {
      "type": "Card",
      "props": { "title": "Productization Review", "description": "Ranked by demo readiness" },
      "children": ["status"]
    },
    "status": {
      "type": "Badge",
      "props": { "label": "Demo ready", "variant": "secondary" },
      "children": []
    }
  }
}
```

Keep the sketch private unless the user asks for JSON.

## Prompt-To-UI Workbench

Render a workbench only when the product itself is a generator:

- Input area: prompt textarea, primary generate action, suggestion chips, and compact hints.
- Preview area: generated content visible immediately from a realistic example.
- State controls: preview/code toggle, version/state selector, copy/open actions.
- Feedback: generation status, validation result, warnings, and debug panel as supporting UI.
- Layout: preview content must not clip. Use responsive grids or contained scroll regions.

## Action-Command Flow

For tasks like "convert my MP4 videos to WebM under 10 MB", render:

- Unified command input with the user's request.
- Auto-analysis panel with detected files, entities, assumptions, and missing specifics.
- Clarification controls only for details needed to proceed.
- Selection controls such as checkboxes, segmented controls, selects, sliders, or steppers.
- Execution state with progress, logs, and disabled/enabled actions.
- Results and feedback with artifacts created, summary, next actions, and recoverable errors.

Avoid a dead-end form. The UI should show the system doing useful inference before asking the user to choose.
