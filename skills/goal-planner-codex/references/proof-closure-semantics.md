# Proof Closure Semantics

Use this reference when intermediate proof states matter. Proof states describe
progress toward evidence closure; verification thresholds decide what is enough
to complete the Goal.

Avoid collapsing meaningful progress into one passed/failed boolean.

## Pattern

```text
declared
-> found
-> readable/reachable
-> produced
-> validated
-> reconciled
-> completion_ready
```

Choose names that match the domain.

## UI Rendering Example

```text
route_created
-> route_validated
-> typecheck_or_build_passed
-> server_http_200
-> screenshots_written
-> screenshots_visually_inspected
-> visual_acceptance_passed
```

## Pull Request Example

```text
requested_changes_found
-> fixes_mapped
-> implementation_updated
-> tests_passed
-> branch_pushed
-> pr_state_verified
-> completion_ready
```

## Runtime Writer Example

```text
intent_declared
-> snapshot_read
-> target_resolved
-> dry_run_passed
-> write_performed
-> runtime_reconciled
-> evidence_recorded
```

## Artifact Delivery Example

```text
sources_declared
-> sources_found
-> sources_readable
-> artifact_rendered
-> filetype_verified
-> content_coverage_verified
-> delivery_ready
```

## Rule

If a proof state could be mistaken for completion but does not actually prove
completion, name it separately.
