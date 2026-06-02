# Extraction Schema Notes

## Goal
Capture page-level events for grounded chronology extraction with explicit uncertainty and evidence anchoring.

## Required page fields
- `page_id`
- `source_pdf`
- `source_page`
- `analysis_pass` (`raw`, `edited`, `reconciled`)
- `entities[]`
- `events[]`
- `uncertainties[]`

## Entity requirements (v2)
- Every entity has:
  - `entity_id`
  - `entity_type`
  - `bbox` (`x,y,w,h` in rendered PNG pixels)
  - `text`
  - `confidence`
  - `chronology_role` (any non-empty role label; VA commonly uses `legal`/`medical`/`admin`)
  - `redaction_recommended` (boolean)
- Generic-only entities are fallback-only and must carry uncertainty note:
  - `"No specific entities detected; generic region fallback was used"`

## Event requirements
- Every event has:
  - `event_id`
  - `event_type` (any non-empty domain label)
  - `summary`
  - `date` (nullable)
  - `date_confidence`
  - `confidence`
  - `condition_tags[]`
  - `evidence[]`
- Every evidence record has:
  - `quote`
  - `bbox_id`
  - `page_ref`
  - `entity_id` (required in reconciled output)

## Edit intent linkage
- `draw_box`, `draw_label`, and `redact_box` must include:
  - `source_entity_id`
  - `entity_type`
  - `label`
  - `style`
  - `priority`
  - `requires_review`

## Uncertainty rule
When data is missing or conflicting, keep it explicit in `uncertainties`.
Do not fabricate dates, outcomes, diagnoses, amounts, or identifiers.
