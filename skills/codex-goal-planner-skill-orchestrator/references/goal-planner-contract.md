# Goal Planner Contract

Use this reference when turning a durable Goal into domain-competent action.

## Minimal Contract

```yaml
goal_frame:
  objective: string
  success_condition: string
  constraints: []
  non_goals: []
  expected_artifacts: []
  risk_level: low|medium|high

skill_intent:
  user_intent: string
  desired_posture: string
  assumptions: []
  semantic_locks: []
  missing_slots: []

phase_plan:
  phases:
    - name: string
      exit_evidence: string

completion_audit:
  requirements:
    - requirement: string
      evidence: string
      status: proved|missing|weak|contradicted
```

## Planner Rule

For trivial goals, the planner may use a raw Tool directly.

For goals involving a domain, runtime State, durable artifacts, or completion
risk, route through:

```text
Goal -> Skill -> Tool Policy -> Tool Adapter -> Tool
```

## Good Defaults

- Ask only for missing slots that materially change the plan.
- Prefer explicit assumptions over hidden assumptions.
- Prefer artifact paths and machine-readable evidence over chat-only summaries.
- Prefer current State reads over memory when State is likely to drift.
- Treat ACKs, successful exits, and file existence as limited evidence unless a
  Skill's Evidence Policy says they are sufficient.

## Completion Audit

Before completion:

1. Restate explicit requirements.
2. Identify current evidence for each requirement.
3. Decide whether each item is proved, missing, weak, or contradicted.
4. Continue work unless every required item is proved by adequate evidence.
