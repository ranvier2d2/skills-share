# Output Contracts

## Timeline Answer

Use this shape for user-facing answers:

```md
## Answer

[Direct answer.]

## Timeline

- `00:12.3` Evidence `ev_001`: [Observed state/action.]
- `00:18.9` Evidence `ev_004`: [Observed state/action.]

## Uncertainties

- [What was unclear and why it matters.]

## Reinspection Targets

- `00:18-00:24`: [Reason to inspect again.]
```

## Evidence Index Validation

An evidence index is valid when:

- video duration is present and positive
- every timestamp is numeric
- every timestamp is within video duration
- timeline-like arrays are monotonic when ordered
- every observation evidence id resolves to an evidence pointer
- uncertainty entries explain the limitation
- interval fields satisfy `t_start < t_end`
- `feedback` entries match the schema and optional `suggested_window` bounds

Schema enforces required fields and basic types. `scripts/validate_evidence_index.py` enforces cross-field checks such as timestamp bounds, monotonic ordering, interval ordering, and observation evidence-id resolution.

## Feedback Input

Represent feedback as:

```json
{
  "kind": "missed_moment",
  "text": "You missed the inbox search failure.",
  "target": "search failure",
  "suggested_window": null,
  "priority": "high"
}
```

Feedback should change the next inspection target, not merely append an apology.
