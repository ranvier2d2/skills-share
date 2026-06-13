# CodeFleet

This context defines the language of a skill that coordinates many coding agents across isolated worktrees, dependency-aware execution, review gates, and final release preparation.

## Language

**Fleet Run**:
A single orchestrated execution of multiple coding tasks toward one user goal.
_Avoid_: Batch, swarm, campaign

**Orchestrator**:
The coordinating agent that decomposes work, owns the dependency graph, gates wave execution, and arbitrates results. It does not perform task implementation directly.
_Avoid_: Worker, implementer, parent coder

**Worker**:
A task-scoped coding agent responsible for completing one task node and producing a checkpoint bundle.
_Avoid_: Subtask, reviewer, helper

**Task Node**:
A bounded unit of work in a fleet run's dependency graph.
_Avoid_: Bullet, todo, item

**Dependency Graph**:
The approved directed graph of task nodes and dependency edges that determines which work may run in parallel.
_Avoid_: Task list, checklist, plan

**Ready Set**:
The task nodes whose blocking dependencies have already been satisfied and may run together.
_Avoid_: Random batch, queue

**Wave**:
A ready set executed in parallel and integrated before dependent tasks begin.
_Avoid_: Batch, phase, round

**Blocking Dependency**:
A dependency edge where downstream work must wait until upstream work produces a reviewed checkpoint bundle.
_Avoid_: Hard dependency, ordering hint

**Soft Dependency**:
A dependency edge where tasks may run in the same wave, but their interaction must be checked later as a seam obligation.
_Avoid_: Non-dependency, ignore, advisory note

**Checkpoint Bundle**:
The evidence and produced contract or artifact that makes a task safe for dependent work to consume.
_Avoid_: Done message, summary, commit only

**Seam Obligation**:
A named cross-task compatibility concern that must be checked during wave integration and the global seam gate.
_Avoid_: Cleanup, review note, merge chore

**Fleet Ledger**:
The persistent orchestration record for a fleet run: graph shape, wave status, checkpoints, seam obligations, and verification evidence.
_Avoid_: Scratch pad, chat history, status vibes

**Wave Integration**:
The act of combining a completed wave and checking its checkpoints and seam obligations before unlocking dependent work.
_Avoid_: Final merge, branch pileup, octopus merge

**Global Seam Gate**:
The final release-readiness check after all waves have been integrated. It checks cross-wave coherence rather than re-reviewing every task from scratch.
_Avoid_: Full rework, first integration, rubber stamp

**Release Branch**:
The final branch prepared from the latest verified wave integration for PR review and shipping.
_Avoid_: Integration branch, task branch, worker branch

**Material Contract Change**:
A discovered change to API, schema, shared component, data model, auth, or user-visible behavior that changes the approved graph or scope.
_Avoid_: Implementation detail, normal refactor

**Reapproval Event**:
A discovery that invalidates the approved dependency graph and requires the user to approve the revised execution plan before the fleet continues.
_Avoid_: Normal progress update, worker question
