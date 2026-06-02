# Visual Quality Checklist

Use this before returning visual, interactive, screenshot-inspired, or ambiguous rendered artifacts.

## Intent Fit

- Make the first screen the artifact itself: tool, dashboard, report, diagram, gallery, form, or prototype.
- Do not create a marketing page unless the user asked for one.
- Preserve explicit nouns, quantities, workflows, and constraints from the prompt.
- Convert vague asks into concrete sample data and realistic interface states.
- Confirm the UI answers the user's decision, workflow, or demo need rather than merely decorating the topic.

## Local Design System Proof

- If Shadcn is detected, use local `components/ui` imports for common primitives.
- If json-render catalog/registry files are detected, ensure saved UI tree component types match them.
- Do not recreate local buttons, badges, cards, sheets, tabs, or controls with ad hoc CSS.
- Match nearby route density, import aliases, and Tailwind token usage.

## Layout

- Check desktop and mobile widths.
- Avoid page-level horizontal scrolling.
- Use bounded scroll regions only when content is inherently wide, such as tables, timelines, code, carousels, or generated previews.
- Keep repeated cards in responsive grids or contained scrollers so the last item is not clipped.
- Do not put cards inside cards. Use full-width sections, panels, tables, or lists for structure.
- Give fixed-format UI stable dimensions with `minmax`, `aspect-ratio`, `min-height`, or explicit control sizes.

## Typography And Color

- Do not scale font sizes with viewport units.
- Keep `letter-spacing` at `0` except small positive values for uppercase metadata.
- Avoid one-note palettes dominated by a single hue family.
- Avoid decorative orbs, blobs, and purely atmospheric backgrounds.
- Make headings match the container: compact panels need compact headings, not hero type.
- Do not accept bare default Shadcn as "styled" unless the user explicitly asked for a plain wireframe or no styling.
- Prefer existing semantic tokens, `var(--chart-*)`, component variants, and route-local `color-mix()` accents over arbitrary raw color utilities.
- Use color and token treatment to encode meaning: status, risk, category, progress, selection, or grouping.

## Content

- Replace generic "Item 1", "Image", "Card", filler Latin text, and unfinished copy with domain-specific content.
- Use plausible labels, statuses, metric names, and actions.
- Keep visible text inside controls and panels without overlap.
- Use visual assets only when they help inspect the thing being requested; avoid broken or fake image references.
- Surface assumptions and missing information in the UI when they affect trust.

## Interaction

- Include useful default, empty, loading, success, warning, and error states when the artifact implies a workflow.
- Ensure buttons and controls have accessible names, focus styles, and stable hit areas.
- Keep JavaScript defensive: missing elements should not break the page.

## Target-Specific Proof

- **Next/Shadcn route:** run `validate_shadcn_route.py`, project type-check/build when available, and browser proof.
- **Global Shadcn render host route:** run `ensure_global_shadcn_host.py --json`, `validate_shadcn_route.py --cwd <host> --route-file <route>`, host type-check/build, and browser proof.
- **json-render tree:** run `validate_ui_tree.py` with catalog and registry when available.
- **Standalone HTML:** run `validate_html_artifact.py --strict`.
- Validators are structural checks, not visual proof. They do not catch every mobile clipping, overflow, contrast, or density issue.

## Browser Proof

- Open the artifact in a browser when possible.
- For file or URL artifacts, you can use `scripts/browser_proof.py --file <artifact.html> --output-dir <dir> --json` or `scripts/browser_proof.py --url <url> --output-dir <dir> --json` when a Chrome-compatible browser is available.
- Inspect a desktop viewport and a narrow mobile viewport.
- Fix overlap, clipping, unreadable text, broken controls, blank regions, console errors, and page-level horizontal overflow before final response.
- If browser proof is blocked by sandbox networking, missing browser tooling, locked dev servers, or local port restrictions, record the blocker and fall back to screenshots from another available browser mechanism, build/type checks, and route/html validators.
