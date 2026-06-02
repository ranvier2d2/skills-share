# Tool Adapter Maturity

Use this reference when deciding how formal a Tool Adapter should become.

## Ladder

```text
Level 0: Raw Tool
  It can act or inspect, but has no agent-facing contract.

Level 1: Documented Tool Adapter
  The Skill says when to use it, what it risks, and what evidence it should
  produce.

Level 2: Executable Tool Adapter
  A script or CLI provides --help, structured output, dry-run behavior for
  mutation, and recoverable errors.

Level 3: Verifiable Tool Adapter
  Adds schemas, snapshots, diffs, Evidence Emitters, and completion-audit
  support.
```

## Promotion Rules

Promote by risk, repetition, and evidence needs.

- Only observes: may remain Level 1.
- Coordinates repeated or order-sensitive steps: promote to Level 2.
- Mutates runtime, can cause State Drift, or can create false confidence about
  completion: promote to Level 3.

## Ownership

A Tool Adapter normally starts as Skill-owned. Extract it into a shared adapter
when two or more Skills need the same operationalized capability with a
compatible Evidence Policy.

## CLI Expectations for Level 2+

- `--help`
- subcommands for multiple operations
- `--json` for machine-readable output
- `--dry-run` for side-effecting operations
- structured recoverable errors
- stdout for machine results, stderr for human diagnostics
- explicit output paths for durable artifacts
