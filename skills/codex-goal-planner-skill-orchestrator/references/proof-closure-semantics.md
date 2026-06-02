# Proof Closure Semantics

Use this reference when defining evidence states for an artifact, Tool Adapter,
runtime operation, or delivery workflow.

Proof Closure Semantics names how closed the evidence is. It is not the same as
Verification Threshold: proof states describe progress; thresholds decide what
is enough to close.

## Pattern

```text
declared
-> found
-> readable/reachable
-> produced
-> validated
-> reconciled
-> delivery_ready/completion_ready
```

Choose states that match the domain. Avoid a single boolean when intermediate
proof states matter.

## Example: Context PDF Delivery

```text
sources_declared
-> sources_found
-> sources_readable
-> html_rendered
-> pdf_rendered
-> pdf_filetype_verified
-> page_count_verified
-> source_coverage_verified
-> delivery_ready
```

## Example: UI Rendering

```text
route_created
-> route_validated
-> typecheck/build_passed
-> server_http_200
-> screenshots_written
-> screenshots_visually_inspected
-> visual_acceptance_passed
```

## Example: Runtime Writer

```text
intent_declared
-> snapshot_read
-> target_resolved
-> dry_run_passed
-> write_performed
-> runtime_reconciled
-> evidence_recorded
```

## Rule

If a proof state could be mistaken for completion but does not actually prove
completion, name it separately.
