# Tool Adapter Maturity

Use this reference when deciding whether direct tool use is enough or a Goal
needs a stronger operational contract.

## Ladder

```text
Level 0: Raw Tool
  The tool can act or inspect, but no agent-facing contract wraps it.

Level 1: Documented Tool Adapter
  A Skill or reference says when to use the tool, what it risks, and what
  evidence it should produce.

Level 2: Executable Tool Adapter
  A script or CLI provides --help, structured output, dry-run behavior for
  mutation, and recoverable errors.

Level 3: Verifiable Tool Adapter
  Adds schemas, snapshots, diffs, evidence emitters, and completion-audit
  support.
```

## Selection Rules

- Trivial or read-only work may stay at Level 0.
- Low-risk repeated practice should usually become Level 1.
- Repeated or order-sensitive operations should promote to Level 2.
- Runtime mutation, state drift, external side effects, or high false-completion
  risk should promote to Level 3.

## Scripts And Hooks

Do not add scripts or hooks just because the contract can imagine them. Add
them when repeated failures, fragile order, or enforcement needs make manual
practice unreliable.

Useful future enforcement surfaces:

```text
scripts/validate_goal_contract.py
scripts/render_completion_audit.py
scripts/pressure_test_goal_planner.py
hooks/pre-completion-audit
```

## Level 2+ CLI Expectations

- `--help`
- subcommands for multiple operations
- `--json` for machine-readable output
- `--dry-run` for side-effecting operations
- structured recoverable errors
- stdout for machine results
- stderr for human diagnostics
- explicit output paths for durable artifacts

## Ownership

A Tool Adapter normally starts as Skill-owned. Extract it into shared tooling
when two or more Skills need the same operationalized capability with compatible
evidence needs.
