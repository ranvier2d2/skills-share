---
name: codex-goal-planner-skill-orchestrator
description: Use when a Codex goal needs to be decomposed through a domain Skill with explicit intent, state, evidence policy, verification threshold, tool routing, Tool Adapters, and completion audit. Trigger for durable /goal work, multi-tool tasks, runtime/artifact workflows, or any situation where completion could be falsely claimed from weak evidence.
---

# Codex Goal Planner Skill Orchestrator

## Contract

This Skill does not replace the planner. It gives the planner a practice
contract:

```text
Goal -> Skill -> Tool Policy -> Tool Adapter -> Tool -> Evidence -> Completion Audit
```

Use it to keep durable goals aligned with domain language, current State, and
proof-based completion.

## Activate When

- The user creates or resumes a durable `/goal`.
- A task spans several steps, tools, artifacts, runtime states, or sessions.
- A raw Tool could produce misleading confidence about completion.
- A domain Skill should govern how the work is practiced.
- The agent must decide between raw Tool use, documented Tool Adapter use, or a
  more formal executable/verifiable adapter.

Skip for trivial one-step requests where a raw Tool is enough, such as checking
the current time or listing a directory.

## Workflow

1. Build a concise `GoalFrame`: objective, success condition, constraints,
   non-goals, expected artifacts, and risk level.
2. Select the domain Skill(s) that should govern the practice. If none exists,
   name the missing Skill instead of pretending a raw Tool is enough.
3. Extract or infer `SkillIntent`: desired posture, assumptions, semantic locks,
   missing slots, and allowed mutation level.
4. Choose Tool Policy before Tool use. Prefer:
   - raw Tool only for trivial or read-only work,
   - documented Tool Adapter for low-risk observed practice,
   - executable Tool Adapter for repeated/order-sensitive practice,
   - verifiable Tool Adapter when runtime mutation, State Drift, or false
     completion risk exists.
5. Execute through the selected Tool Adapter when available.
6. Track Proof Closure Semantics. Do not collapse evidence into one
   passed/failed boolean.
7. Run Completion Audit before claiming the Goal is complete.

## Required Distinctions

- Goal: what must become true.
- Planner: chooses next action.
- Skill: governs competent practice.
- Tool: external capability.
- Tool Adapter: operational contract around a Tool.
- Tool Policy: decision boundary for tool use.
- State: current actionable truth.
- Evidence Policy: what proof matters.
- Verification Threshold: how much proof is enough.
- Proof Closure Semantics: named intermediate states of proof.

## Resource Index

- `references/goal-planner-contract.md`: read when forming the GoalFrame,
  SkillIntent, phase plan, and Completion Audit.
- `references/tool-adapter-maturity.md`: read when deciding whether a Tool
  should stay raw/documented or become executable/verifiable.
- `references/proof-closure-semantics.md`: read when defining proof states for
  an artifact, runtime operation, or delivery workflow.
- `references/examples.md`: read when you need a concrete pattern; includes the
  context PDF delivery adapter as the first canonical example.

Set `GOAL_PLANNER_CONTEXT_ROOT` to the workspace that contains the goal-planner context files.

Canonical workspace glossary:
`$GOAL_PLANNER_CONTEXT_ROOT/CONTEXT.md`

Conceptual reference:
`$GOAL_PLANNER_CONTEXT_ROOT/docs/conceptualizacion-skill-goal-planner.md`

First executable Tool Adapter:
`$GOAL_PLANNER_CONTEXT_ROOT/scripts/context_pdf_delivery_adapter.py`

## Completion Rule

Do not mark a goal complete merely because the current plan looks plausible or
a command returned success. Completion requires current evidence for each
explicit requirement, checked against the relevant Verification Threshold.
