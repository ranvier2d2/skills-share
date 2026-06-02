# JSON Render Pattern

Use this pattern when a user asks for a prompt-to-UI generator, a rendered result from natural language, a JSON-driven UI, or an app that behaves like the json-render playground.

## Source Inspiration

The `jsonrender-2-adv-5.zip` project uses this core flow:

1. Accept one natural-language prompt.
2. Map the prompt to a component plan.
3. Generate a structured UI tree.
4. Validate the tree.
5. Render the tree into visible UI.
6. Provide suggestions, code/preview toggles, copy actions, and debug/status feedback.

The important transferable pattern is the schema-driven pipeline, not the exact React/shadcn implementation.

## Internal Component Plan

Before writing HTML, sketch a small flat tree:

```json
{
  "root": "root-workspace",
  "elements": [
    {
      "key": "root-workspace",
      "type": "Stack",
      "props": { "direction": "vertical", "gap": "md" },
      "children": ["header", "main-panel"]
    },
    {
      "key": "header",
      "type": "Heading",
      "props": { "level": 1, "content": "Generated UI" },
      "children": []
    }
  ]
}
```

Keep the plan private unless the user asks for JSON. Use it to ensure every visible section has a purpose and no child points to a missing element.

## Component Vocabulary

Use these primitives as a planning vocabulary, then render them as semantic HTML:

- `Stack`: layout group, vertical or horizontal.
- `Grid`: responsive collection or dashboard layout.
- `Card`: grouped item, preview, metric, or repeated content.
- `Heading`: section title or page title.
- `Text`: supporting copy or body content.
- `Button`: clear command or call to action.
- `Input` / `Textarea` / `Select`: user-provided details.
- `Badge`: status, category, or metadata.
- `Alert`: validation, warning, success, or next step.
- `Image` / `Avatar`: media placeholders only when the prompt implies visual content.
- `Progress` / `Log`: execution state for action-command workflows.
- `Table`: dense operational data.

## Prompt-To-UI Workbench

When the product is itself a generator, render a usable workbench:

- Left panel: prompt textarea, keyboard hint, primary generate button, suggestion chips, status/debug area.
- Right panel: framed preview with realistic generated content and overflow behavior.
- Top controls: preview/code toggle, version or state selector, copy/open actions when useful.
- Empty state: show what will appear, not generic instructions.
- Generated result: visible immediately after the first sample prompt; do not make the user imagine the output.

## Clarification And Auto-Execution

For natural-language action tools, avoid a dead-end form. Show progression:

1. **Unified input**: one command box with the user's intent.
2. **Auto-analysis**: detected files, entities, components, or assumptions.
3. **Clarification only if needed**: compact choices for missing specifics.
4. **User selection**: checkboxes, segmented controls, selects, or sliders.
5. **Execution**: progress, log, and disabled/active states.
6. **Results**: success/failure summary, artifacts created, and next actions.

## Validation Rules

- The root key must match an element.
- Every child key must exist.
- Every element needs a stable key, type, props object, and children array.
- Prefer a container root (`Stack`, `Grid`, `Card`, or `main` layout).
- Render unknown components as visible fallback blocks during prototyping.
- Include error/status surfaces in generated workbenches so failed generation is explainable.
