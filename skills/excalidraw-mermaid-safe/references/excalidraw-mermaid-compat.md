# Excalidraw Mermaid Compatibility Notes

This skill is tuned for Excalidraw Mermaid import workflows.

## Safe assumptions

- Prefer `flowchart` diagrams for predictable imports.
- Quote node labels (`A["Label"]`) to reduce parser ambiguity.
- Remove markdown link syntax from labels.
- Remove raw URLs from labels because URL punctuation can break Mermaid node parsing.
- Truncate labels that would make Excalidraw imports hard to scan.
- Use conservative style keys in `classDef`:
  - `fill`
  - `stroke`
  - `stroke-width`
  - `color`

## Parser-safe style strategy

- Semantic classes only: `source`, `finding`, `decision`, `action`, `risk`, `neutral`.
- Avoid advanced Mermaid theming and renderer-specific directives.
- Keep layout readable through grouping (`subgraph`) and node caps.

## Known risky patterns

- Nested markdown links in labels like `[[Text](url)]`.
- Raw URLs inside labels.
- Overly dense one-node-per-line auto conversions.
- Non-flowchart diagram declarations when importing as flowchart in Excalidraw.

## Fixture coverage

The regression fixtures cover:

- Basic markdown outline to grouped flowchart.
- Markdown links and raw URLs inside Mermaid node labels.
- Existing Mermaid code blocks with unsafe inline styles removed.
- Markdown task checkboxes, simple tables, and numbered risks.
- Long labels that should be truncated before output.
