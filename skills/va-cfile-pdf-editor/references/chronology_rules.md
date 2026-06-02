# Chronology Rules

## Timeline classes
- Legal chronology: filings, decisions, appeals, administrative case events.
- Medical chronology: exams, diagnoses, treatments, imaging, condition progression.
- All-events chronology: every extracted event regardless of type.
- Non-VA profiles may use any `event_type`; preserve labels as-is.

## Date handling
1. Use ISO date when available.
2. If unresolved, keep `date: null` and add uncertainty.
3. During sorting, place undated events after dated events.

## Reconciliation preference
1. Prefer edited-pass event when confidence improves and evidence is retained.
2. Preserve raw-pass event when edited-pass confidence drops or evidence is lost.
3. Record unresolved conflicts in reconciliation report and QA report.

## Citation rule
Every chronology row must map to at least one source citation.

## Entity linkage rule
Every chronology row must include at least one citation with both:
- `entity_id`
- `bbox_id`

Rows lacking entity-linked citations are considered validation failures.

## Compatibility outputs
- Always emit `legal_*` and `medical_*` files for VA compatibility.
- Also emit `all_events_*` files for general-purpose extraction workflows.
