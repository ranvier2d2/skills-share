# Task 002 - Real PDF Run and Calibration

## Status
COMPLETED

## Goal
Run the full `va-cfile-pdf-editor` v2 pipeline on real sample PDFs and validate precision annotation behavior against expected entity-level targets.

## Scope
- Use the fixed vision-first order from `SKILL.md`.
- Use `codex_findings_v2` JSON for raw and edited passes.
- Use optional `annotation_review.json` only when medium-confidence entities need correction.

## TODO
- [x] Prepare a real-case `case_id` and input PDF set.
- [x] Produce raw page renders under `output/pdf_cases/<case_id>/pages/raw/`.
- [x] Build raw findings file in `extractions/raw/codex_findings.json` with entity-rich detections.
- [x] Run derive and review stages to produce `edit_intents_final.json`.
- [x] Verify edited PNG overlays for entity precision and label placement.
- [x] Run edited-pass analysis and reconcile outputs.
- [x] Build chronology artifacts and validate citation completeness.
- [x] Record unresolved low-confidence entities and update thresholds if needed.

## Run Notes (2026-02-12 Rerun)
- `case_id`: `JEROME_SAMPLE_001`
- Sample PDF generation (`pdf` skill, `reportlab`): `output/pdf/jerome_sample_set_001/*.pdf` (10 polished files)
- Input PDFs: `output/pdf_cases/JEROME_SAMPLE_001/input_pdfs/*.pdf` (10 files, refreshed from sample set)
- Derived and reviewed edit ops: 120 total (12 per page), all auto-kept in auto-review mode.
- Overlay verification: 10/10 edited PNGs changed relative to raw PNGs.
- Raw findings citation links: 30/30 rows include both `entity_id` and `bbox_id`.
- Edited findings citation links: 30/30 rows include both `entity_id` and `bbox_id`.
- Citation quality: 60 chronology citation rows, 0 missing entity links, 0 missing bbox ids, 0 missing quotes.
- Low-confidence entities below 0.50: 0 (no threshold tuning needed in this run).
- Validator: `scripts/validate_bundle.py` passed.

## Expected Output
- Valid bundle at `output/pdf_cases/<case_id>/`.
- Passing `scripts/validate_bundle.py`.
- Brief calibration notes added to memory.
