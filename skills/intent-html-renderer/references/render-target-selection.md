# Render Target Selection

Use this before writing files. The goal is to choose the strongest available target from evidence, not from habit.

## Decision Rule

If a React/Shadcn/json-render app is detected and the user did not explicitly ask for a portable single-file artifact, do not create standalone HTML. Use the local UI system and validate that usage.

If no usable local UI system is detected and the user did not explicitly ask for a portable single-file artifact, use the global Shadcn render host before falling back to standalone HTML. The absence of local app dependencies is not a reason to produce a low-fidelity or unstyled artifact.

Explicit portable language wins over environment detection. Examples: "portable HTML", "standalone HTML", "single-file HTML", "self-contained HTML", "send to a teammate", "open as a file", or "HTML file I can share".

## Target Matrix

| Target | Choose When | Required Evidence | Output Location | Required Validation |
| --- | --- | --- | --- | --- |
| Next/Shadcn route | The repo has App Router plus Shadcn components and the user asks for a usable screen, dashboard, report, workbench, or prototype. | `package.json` with Next/React, `app/`, `components.json`, `components/ui`. | Existing app route, usually `app/<slug>/page.tsx` under the detected app package. | `validate_shadcn_route.py`, project type-check/build, desktop/mobile browser proof. |
| json-render Shadcn tree or preview | The product itself is JSON-driven rendering, prompt-to-UI, catalog validation, or renderer integration. | `shadcn-catalog.ts`, `shadcn-registry.tsx`, json-render imports, renderer route or playground. | Saved UI tree fixture, renderer route, or playground integration as appropriate. | `validate_ui_tree.py --catalog ... --registry ...`, project type-check/build, preview proof. |
| Existing React route without Shadcn | The repo has React/Next but no Shadcn, and app output is still more appropriate than portable HTML. | React/Next app files, existing components or design tokens. | Existing app route/component. | Project type-check/build and browser proof. |
| Global Shadcn render host | The current workspace has no usable UI dependencies, installing app deps would pollute the repo, and the user did not ask for portable HTML. | `~/.codex/render-hosts/intent-html-renderer-shadcn/package.json`, `components.json`, `components/ui`, `node_modules`, and `app/artifacts`. | `~/.codex/render-hosts/intent-html-renderer-shadcn/app/artifacts/<slug>/page.tsx`. | `ensure_global_shadcn_host.py --json`, `validate_shadcn_route.py --cwd <host> --route-file <route>`, host type-check/build, desktop/mobile browser proof. |
| Standalone HTML | The user asks for a portable HTML file, wants a self-contained artifact, the task is outside a repo and the global host cannot be bootstrapped, or the user explicitly asks for no dependencies. | Explicit portable-file request, or documented host bootstrap blocker. | A self-contained `index.html` or named `.html` artifact. | `validate_html_artifact.py <file> --strict`, desktop/mobile browser proof. |
| Prompt-to-UI workbench | The UI being built is itself a generator, natural-language command tool, or preview/code workbench. | Prompt workflow requested or existing renderer/playground context. | Native route when app exists; global host when no local app exists; standalone only for explicit portable output or host blocker. | Target-specific validation plus workbench state checks. |

## Evidence Checklist

Before choosing standalone HTML in a repo, check for:

- `AGENTS.md` or nested app guidance.
- Root and app-level `package.json`.
- App Router directories such as `app/`, `apps/*/app/`, or `src/app/`.
- Shadcn config: `components.json`.
- Shadcn primitives: `components/ui`.
- json-render catalog and registry files.
- Existing routes that demonstrate layout, import aliases, and UI density.
- Global Shadcn render host readiness via `scripts/ensure_global_shadcn_host.py --json`.

## Output Rules

- Use the repo's existing route structure and import aliases.
- Use local UI primitives instead of recreating buttons, cards, tabs, badges, sheets, or controls with ad hoc CSS.
- Keep route-specific sample data in the route/component unless the repo already has a fixture convention.
- For temporary validation samples, put fixtures in the skill `assets/` folder rather than polluting the app.
- If a validation route is created only for pressure testing, remove it before final response unless the task explicitly asks to keep it.
- In subagent or temporary forks, use unique route/file names and avoid modifying the main app unless that is the test objective.
- Generated host artifacts live under `~/.codex/render-hosts/intent-html-renderer-shadcn/app/artifacts/<slug>/page.tsx`; do not write generated artifacts inside the skill source directory.

## Proof Rules

Each completed artifact needs:

- Path to the artifact.
- Target decision and local evidence used.
- Validation commands and results.
- Browser proof when the artifact is visual and a browser can run it.
- If dependency installs, local ports, or browser tools are blocked, state that explicitly and provide the strongest available validator/build evidence.
- Any assumptions surfaced in the UI, not only in the final message.
