---
name: goal-planner
description: Plan, start, inspect, budget, and complete Codex Goals. Use when the user asks to create a goal, define a goal, plan a goal, refine an objective, set a token budget, check current goal status, continue toward an active goal, replace a goal, or close a goal after verifying completion. Use request_user_input when available to resolve bounded ambiguity before calling create_goal.
---

# Goal Planner

## Overview

Turn vague intent into a concrete Codex Goal with an objective, completion criteria, scope, and budget. Use native goal tools when available; fall back to plain chat only when a needed goal tool is unavailable.

Do not use this skill for ordinary task planning unless the user explicitly asks for a Codex Goal, goal budget, active goal status, or goal completion.

## Lifecycle Rules

1. Inspect current state with `get_goal` when available.
2. If a goal is active, continue it by default. Do not create another goal unless the user explicitly asks to replace it or start a separate goal.
3. If a completed goal still blocks new goal creation, explain that it must be cleared or replaced using available Goal tooling before creating a new one.
4. Create a goal only when the user explicitly asks to start/create/set a goal, or confirms a proposed goal.
5. Set `token_budget` only when the user explicitly gives one or chooses one during clarification.
6. Before marking a goal complete, audit the objective against real evidence and call `update_goal(status="complete")` only when nothing required remains.

## Clarification Protocol

Clarify only what changes the goal. If the answer can be inferred from local files, tool state, or prior conversation, inspect that evidence instead of asking.

Resolve these fields:

- Objective: the concrete outcome the user wants.
- Success criteria: how completion will be judged.
- Scope boundaries: what is included, excluded, or intentionally deferred.
- Budget/depth: token budget, time box, or level of rigor.
- Replacement policy: whether an active goal should be continued, completed, or replaced.

Ask as many questions as needed, but no more than necessary. Stop when remaining ambiguity is low enough to proceed without likely surprising the user.

Prefer `request_user_input` for bounded choices such as budget/depth, scope option, replacement policy, or whether to proceed. Use normal chat for open-ended answers. Keep each `request_user_input` call to one to three short questions.

Each clarification question should:

1. Name the unresolved decision.
2. Provide the recommended answer first when options are available.
3. State the practical tradeoff.
4. Ask for confirmation or correction.

## Goal Shape

Draft goals as one concise outcome sentence. Prefer outcome language over process language.

Good:

```text
Implement and verify dark-mode support for the account settings page.
```

Weak:

```text
Work on dark mode.
```

If useful, summarize before creation:

```text
Proposed goal: <objective>
Success criteria: <criteria>
Scope: <included/excluded>
Budget: <budget or none>
```

Ask for confirmation unless the user's request already specifies the objective and budget clearly.

## Budget Guidance

Do not invent a token budget. If the user wants a budget but has not given one, offer bounded choices through `request_user_input` when available.

Use conservative options such as:

- Small: quick verification or single-file edit.
- Medium: focused implementation with tests.
- Large: research, multi-file work, or iterative validation.

Accept user-provided custom budgets when explicit.

## Completion Audit

Before calling `update_goal(status="complete")`:

1. Restate the goal as concrete success criteria.
2. Map every explicit requirement to evidence: files changed, command output, tests, screenshots, docs, PR state, or direct tool results.
3. Identify missing, weakly verified, or uncovered requirements.
4. Continue work if anything remains uncertain.
5. Complete the goal only when the audit shows the objective is achieved.

After `update_goal` succeeds, report the final token and time usage from the tool result.

## Tool Fallbacks

- If `get_goal` is unavailable, say that Goal tooling is unavailable in this session and proceed with a plain-text plan.
- If `request_user_input` is unavailable, ask concise normal chat questions.
- If `create_goal` is unavailable, produce the proposed goal text and say Goal creation is unavailable in this session.
- If `update_goal` is unavailable, provide the completion audit and say the goal could not be marked complete by tool.
