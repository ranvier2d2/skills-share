# Launch Review

## Context Inputs
- [x] Product brief includes [migration notes](https://example.com/migration)
- [ ] Customer escalation URL https://example.com/customer/123 should not appear

## Decision Options
| Option | Status | Owner |
| --- | --- | --- |
| Keep current importer | blocked by parser drift | Platform |
| Generate safer Mermaid | recommended | Tools |

## Risks and Issues
1. Raw URLs can break labels
2. Long labels can make Excalidraw imports hard to scan on smaller canvases

## Next Steps
- Add fixture tests
- Run doctor checks before publishing
