# Goal Lifecycle

Use this reference when forming or continuing a native Codex Goal.

## Lifecycle Defaults

1. Inspect current state with `get_goal` when available.
2. Continue an active Goal by default.
3. Create a new Goal only when the user explicitly asks for one or confirms a
   proposal.
4. Set `token_budget` only when explicit.
5. Use `update_plan` for `standard` and `evidence-led` Goals.
6. Complete only after the audit proves every explicit requirement.

The Codex harness may enforce additional lifecycle rules. Follow the current
tool contract when it is stricter or more specific than this reference.

## Native Goal Text

The Goal text is a durable navigation capsule, not the whole operating
contract. It survives chat compaction and should stay compact.

Include:

- objective,
- completion condition,
- rigor level when useful,
- critical file, script, PR, issue, or contract references,
- explicit non-negotiable constraints when short.

Avoid:

- full task lists,
- long evidence matrices,
- implementation diaries,
- speculative details,
- large pasted requirements.

Example:

```text
Implement and verify CSV export for reports. Completion requires working export
behavior, focused tests, and user-visible evidence. Rigor: evidence-led. Follow
~/.codex/goals/current-repo/csv-export-reports/contract.md before completion.
```

## Contract File Ordering

If the Goal text references a contract file, that file must already exist before
`create_goal` is called.

Order for `evidence-led` Goals:

```text
draft contract -> write user-level contract file -> create compact Goal -> update_plan
```

Never create a Goal with a dead contract reference.

## Contract Path

Default path:

```text
${CODEX_HOME:-~/.codex}/goals/<repo-slug>/<goal-slug>/contract.md
```

Prefer user-level contract storage. It keeps execution contracts out of the
project unless the user or repo convention asks for project-local state.

Use repo-local contract storage only when:

- the user explicitly requests it,
- the repo already has a clearly ignored convention for Goal artifacts,
- future agents must find the contract from the worktree without relying on the
  user's home directory.

Before writing repo-local execution state, verify the target path is ignored or
ask first.

## Slug Rules

Auto-create slugs from the repository/workspace name and objective.

- lowercase ASCII,
- kebab-case,
- remove filler words,
- keep important nouns and verbs,
- about six words or fewer,
- append `-2`, `-3`, etc. on collision.

Examples:

```text
Repo: Pixir -> pixir
Implement and verify CSV export for reports -> csv-export-reports
Fix failing checkout redirect tests -> checkout-redirect-tests
Prepare PR for review -> prepare-pr-review
```

## Contract Frontmatter

Use Markdown with YAML frontmatter:

```yaml
---
contract_version: 1
skill: goal-planner-codex
rigor: evidence-led
status: active
created_at: "2026-06-06T00:00:00Z"
updated_at: "2026-06-06T00:00:00Z"
goal_text: "Compact native Codex Goal text"
---
```

Recommended body sections:

```text
# Goal Contract
## Objective
## Success Criteria
## Scope
## Non-Goals
## Definition Recovery
## Skill Route
## Tool Policy
## Evidence Plan
## Proof States
## Completion Audit
## Open Questions
## Contract Changes
```

Omit sections that do not matter for `standard` work. Keep the full shape for
`evidence-led` work when false completion is a real risk.

## update_plan

Use `update_plan` as the live execution state.

- `simple`: no plan required unless helpful.
- `standard`: short task plan with concrete exit points.
- `evidence-led`: task plan tied to proof states and evidence sources.

Keep plans current. Mark steps complete as evidence arrives, not only at the
end.
