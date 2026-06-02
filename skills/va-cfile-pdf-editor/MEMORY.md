# VA C-File PDF Editor - Project Memory

## Current Focus
- Task `003`: add compact findings authoring guidance for `codex_findings_v2` examples now that Task 002 calibration run is complete.
- Task `004`: run Iteration 2 segmentation research benchmark (SAM-family candidates via precomputed adapters) and keep recommendation at prototype-only until human-labeled evaluation is complete.

## Next Focus
- Deliver Task `003` authoring cheat-sheet with valid `codex_findings_v2` examples and entity-bound evidence rows.
- Execute `sam2_precomputed` and `sam3_precomputed` benchmark runs once precomputed segment files are available.

## Task Status
| Task | Status | Next Action |
|------|--------|-------------|
| 001: Precision Annotation Upgrade | COMPLETED | Keep contracts stable and only patch defects found during real-case runs |
| 002: Real PDF Run and Calibration | COMPLETED | Keep generated sample bundle as baseline regression fixture |
| 003: Findings Authoring Guidance | IN PROGRESS | Add a compact codex_findings_v2 authoring cheat-sheet with examples |
| 004: Segmentation Iteration 2 Research | IN PROGRESS | Run SAM-family precomputed comparisons and replace bootstrap labels with human-labeled slices |

## Decisions (Do Not Re-Litigate)
| Decision | Rationale | Date |
|----------|-----------|------|
| Vision-first order is mandatory (raw analysis before edits) | Prevents blind edits and keeps annotation intent evidence-driven | 2026-02-12 |
| OCR/Tesseract fallback remains out of scope for v1 | Keep extraction behavior consistent with Codex visual analysis contract | 2026-02-12 |
| Entity-level boxes are default; broad bands are fallback-only | Improves precision and chronology citation quality | 2026-02-12 |
| Optional review gate is between derive and apply | Supports human correction without changing default auto flow | 2026-02-12 |
| Chronology citations must include entity_id and bbox_id | Enforces auditability from timeline rows to page evidence | 2026-02-12 |

## Last Session Accomplishments
- Added strict findings schema: `schemas/codex_findings_v2.schema.json`.
- Added review schema: `schemas/annotation_review.schema.json`.
- Upgraded edit contract to enforce entity binding for `draw_box`, `draw_label`, `redact_box`.
- Implemented deterministic entity-to-op mapping with confidence gates in `scripts/derive_edit_intents.py`.
- Added review resolution stage in `scripts/review_annotation_intents.py`.
- Upgraded edit renderer styles and label placement in `scripts/apply_page_edits.py`.
- Added entity-aware checks in `scripts/analyze_edited_pages_codex.py`.
- Added entity-level reconciliation metrics in `scripts/reconcile_extractions.py`.
- Added entity-linked chronology and low-confidence QA outputs in `scripts/build_case_bundle.py`.
- Added validator checks for stage order, entity-linked citations, and review artifacts in `scripts/validate_bundle.py`.
- Regenerated `agents/openai.yaml`.
- Confirmed deterministic PNG hash stability in synthetic rerun.
- Executed full real-sample run for `JEROME_SAMPLE_001` across all 9 stages with passing final validator.
- Generated 10 input sample PDFs and produced a complete bundle under `output/pdf_cases/JEROME_SAMPLE_001/`.
- Verified overlay application and entity-level citation linkage completeness (no missing entity or bbox links).
- Regenerated a polished 10-PDF Jerome sample set via `tmp/pdfs/generate_jerome_sample_set_001.py`.
- Re-ran full locked-order pipeline for `JEROME_SAMPLE_001` on refreshed inputs with passing validator on 2026-02-12.
- Added Iteration 2 segmentation research artifacts:
  - `scripts/benchmark_segmentation_iteration2.py`
  - `research/configs/segmentation_benchmark_iteration2.json`
  - `research/segmentation_iteration2.md`
  - `research/segmentation_decision_memo.md`
- Ran mixed-layout benchmark on `CASE_MIXED_LAYOUT_STRESS_001` with feature flag `SEGMENTATION_RESEARCH_V2=1`.
- Recorded prototype-only decision pending SAM-family precomputed runs and human-labeled validation.

## Calibration Snapshot (JEROME_SAMPLE_001, 2026-02-12 Rerun)
- Input PDFs: 10
- Rendered pages: 10
- Final edit operations kept: 120 (auto-review mode, no manual overrides)
- Edited pages changed vs raw: 10/10
- Total reconciled events: 20 (`legal=11`, `medical=9`)
- Citation rows: 60
- Missing quote citations: 0
- Missing entity-linked citations: 0
- Missing bbox-linked citations: 0
- Raw findings event citation rows with `entity_id` + `bbox_id`: 30/30
- Edited findings event citation rows with `entity_id` + `bbox_id`: 30/30
- Low-confidence entities below `0.50`: 0
- Bundle validation: passed (`scripts/validate_bundle.py`)

## Validation Snapshot
- `python3 -m py_compile scripts/*.py` passed.
- `quick_validate.py` passed for:
  - `local/va-cfile-pdf-editor`
  - `pdf` (unchanged)
- Synthetic smoke case passed at `/tmp/va_cfile_precision_smoke2`.

## Known Risks
- Real-world extraction quality still depends on upstream `codex_findings_v2` quality.
- Missing or low-confidence entities can reduce annotation coverage in auto mode.
- Skill directory is not a git repo; local git telemetry is unavailable during flashback.
- Calibration run used generated sample PDFs, not authentic VA C-file scans; real OCR-noise and handwriting edge cases remain untested.
- Segmentation benchmark currently uses bootstrap labels derived from findings artifacts; decision-grade conclusions require human-labeled regions.

## Quick Links
- `SKILL.md`
- `schemas/codex_findings_v2.schema.json`
- `scripts/derive_edit_intents.py`
- `scripts/review_annotation_intents.py`
- `scripts/apply_page_edits.py`
- `scripts/validate_bundle.py`
- `output/flashback/`

## Flashback Checkpoints
- 2026-02-11 `output/flashback/flashback_2026-02-11_2210.md`
- 2026-02-11 `output/flashback/flashback_2026-02-11_2211.md`
