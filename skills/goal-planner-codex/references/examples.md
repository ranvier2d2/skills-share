# Examples

Use these as patterns, not templates to copy blindly.

## Simple Goal

User:

```text
Create a goal to check whether the focused tests pass.
```

Goal text:

```text
Check whether the focused test suite passes and report the exact result.
Completion requires running the requested tests and reporting failures or pass
status.
```

No contract file is needed.

## Standard Goal

User:

```text
Set a goal to add CSV export to reports.
```

Goal text:

```text
Implement and verify CSV export for the reports page. Completion requires the
export flow to work for current report data and focused tests to pass.
```

Plan:

```text
1. Inspect report data flow
2. Implement export action
3. Add focused tests
4. Verify behavior and summarize evidence
```

No contract file is required unless the work becomes long-running or ambiguous.

## Evidence-Led Goal

User:

```text
Make the PR ready for review with tests so it is verifiable as a Goal.
```

Write `${CODEX_HOME:-~/.codex}/goals/current-repo/pr-ready-review/contract.md`
first.

Goal text:

```text
Update the PR and leave it ready for review. Completion requires requested
changes handled, tests passing, branch pushed, and PR state verified as
non-draft. Rigor: evidence-led. Follow
~/.codex/goals/current-repo/pr-ready-review/contract.md.
```

Contract sketch:

```md
---
contract_version: 1
skill: goal-planner-codex
rigor: evidence-led
status: active
created_at: "2026-06-06T00:00:00Z"
updated_at: "2026-06-06T00:00:00Z"
goal_text: "Update the PR and leave it ready for review..."
---

# Goal Contract

## Objective
Update the PR and leave it ready for review.

## Success Criteria
- Requested changes are handled.
- Focused tests pass.
- Branch is pushed.
- PR is verified as non-draft.

## Evidence Plan
- PR comments or requested changes inspected.
- Diff reviewed.
- Test command output captured.
- GitHub PR state queried after push.

## Proof States
requested_changes_found -> fixes_mapped -> implementation_updated ->
tests_passed -> branch_pushed -> pr_state_verified -> completion_ready

## Completion Audit
Record requirement, evidence, and status before completing the Goal.
```

## Discovery Goal

User:

```text
Make this repo better.
```

Definition Recovery should sharpen what "better" means. If the user wants a
Goal before implementation criteria exist, create a discovery Goal:

```text
Identify and prioritize three verifiable repo improvement candidates, with
evidence from code/docs and a recommended next implementation Goal.
```

Completion artifact:

```text
candidate list + evidence + recommended next Goal
```
