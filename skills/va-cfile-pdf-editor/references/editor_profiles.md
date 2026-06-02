# Editor Profiles

## `entity_level_v2` (default)
Targeted deterministic operations derived from entity findings in raw pass:
- `draw_box` + `draw_label` for entity-level evidence (all non-generic entities).
- `redact_box` when `redaction_recommended=true`.
- `deskew`/`rotate`/`contrast`/`denoise`/`crop` remain available but are not the primary v2 path.

## Entity class mapping
- Annotation entities: any entity type except generic broad-region fallback classes.
- Redaction entities: any entity with `redaction_recommended=true`.
- VA defaults still apply semantic colors for legal/medical/metadata when labels match those classes.

## Confidence gates
- `confidence >= 0.75`: auto-apply.
- `0.50 <= confidence < 0.75`: set `requires_review=true`.
- `confidence < 0.50`: do not auto-apply; emit uncertainty.

## Semantic style map
- Legal evidence boxes: red.
- Medical evidence boxes: blue.
- Metadata/other evidence boxes: orange.
- Redactions: black fill.

## Important
- Do not apply any operation before raw visual analysis and intent derivation.
- No blind preprocessing pass is allowed.
- Generic broad-region boxes are fallback-only and must be uncertainty-flagged.
