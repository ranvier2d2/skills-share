# Intent Inference Rubric

Use this when the user states an outcome but does not specify the UI.

## Infer The Surface

- "Track", "manage", "organize", "CRM", "admin", "workflow": render an operational surface with tables, filters, status, details, and actions.
- "Explain", "teach", "summarize", "report", "brief": render a document/report surface with hierarchy, evidence, callouts, and navigation aids.
- "Compare", "choose", "rank": render a decision surface with criteria, tradeoffs, recommendation, and supporting details.
- "Productize", "package", "demo", "sales", "bundle": render a productization decision surface with readiness, packaging gaps, bundle fit, demo path, and next actions.
- "Visualize", "map", "flow", "process": render a diagram or staged process with clear relationships and labels.
- "Landing", "launch", "sell", "promote": render a first-viewport page where the product or offer is visible immediately.
- "Calculator", "simulator", "quiz", "planner": render an interactive tool with inputs, outputs, validation, and useful defaults.
- "Command", "convert", "process", "run", "automate": render an action-command workflow with unified input, detected assumptions, clarification controls, progress, logs, and results.
- "Create UI", "generate UI", "render from prompt": render the requested UI directly unless the product itself is a generator.

## Product-Intent Score

Before implementing, score the intended UI informally against these questions:

- Does the first screen answer the user's real decision or job?
- Are the primary entities named with domain-specific labels?
- Are tradeoffs, gaps, statuses, or next actions visible without reading the original prompt?
- Does the surface include useful states when the task implies a workflow?
- Does the chosen artifact target match local repo evidence?

If the answer is weak, adjust the surface before writing code.

## Decide Without Offloading

- Do not ask the user to choose layout, component library, card counts, navigation, or controls.
- Ask only when two or more materially different products could satisfy the same prompt.
- When ambiguity is tolerable, pick the strongest default and show assumptions inside the artifact.
- Prefer realistic sample data over empty stand-ins.
- Preserve explicit quantities. If the user asks for five videos, render five videos.

## Content Assumptions

- Use domain-specific labels instead of generic "Item 1" copy.
- Include useful empty, loading, success, warning, and error states when the intent implies a workflow.
- Make the primary action or insight visually dominant.
- Keep repeated content inspectable with responsive grids or contained scrollers.
- Make the artifact understandable without the original prompt.
- Surface assumptions inside the UI as badges, notes, filters, or evidence rows when they affect interpretation.
