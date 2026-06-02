# Jerome Workflow Playbook

## Objective
Turn VA C-file PDFs into a searchable, citation-grounded legal and medical chronology bundle.

## Operator sequence
1. Ingest source PDFs and render all pages.
2. Perform Codex visual analysis on raw pages.
3. Derive deterministic edit intents from raw extraction.
4. Optional review checkpoint:
   - Review medium-confidence intents (`requires_review=true`).
   - Approve/reject entities and override boxes via `annotation_review.json`.
5. Apply final edits and annotations to page PNGs.
6. Perform second Codex visual analysis on edited pages.
7. Reconcile extraction passes.
8. Build chronology artifacts and citation map.
9. Validate before delivery.

## Delivery checklist
- Legal chronology produced.
- Medical chronology produced.
- Citation map complete.
- QA report includes unresolved uncertainty.
- QA report includes unresolved low-confidence entities.
- No chronology row without citation.
