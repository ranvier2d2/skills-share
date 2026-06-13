# DependencyGraph Workflow

Build the dependency graph before spawning workers. The fleet runs in parallel
only across the current ready set: tasks with no unresolved blocking
dependencies.

## Goal

Turn a high-level goal or user-supplied task list into a reviewed DAG that the
user approves before execution.

## Step 1 - Map Tasks

If the user supplied a high-level goal, decompose it into concrete task nodes.
If the user supplied tasks, keep their intent but still analyze dependencies.

Each task must have:

```json
{
  "id": 1,
  "slug": "api-contract",
  "goal": "Define the order API contract",
  "depends_on": [],
  "produces": ["order API request/response contract"],
  "consumes": [],
  "touches": ["src/api/orders.ts"],
  "blocking_risk": "none",
  "parallel_group": 1
}
```

## Step 2 - Classify Edges

Every dependency edge is either `blocking` or `soft`.

- `blocking`: downstream work must not start until the upstream task emits a
  reviewed checkpoint bundle.
- `soft`: tasks may run in the same wave, but the edge creates a seam
  obligation that must be checked at wave integration and final merge.

Blocking examples:

- UI depends on an API/schema not yet defined.
- Tests depend on final behavior from an implementation task.
- Migration depends on the agreed data model.
- Shared component extraction must happen before feature pages reuse it.
- Auth or permission semantics must be decided before dependent flows use them.

Soft examples:

- Two tasks touch nearby CSS but not the same component contract.
- One task updates docs while another updates implementation.
- Two routes share a layout component but do not change its public props.
- Two backend handlers share test utilities but not runtime contracts.

## Step 3 - Use A Mapper, Then An Arbiter

Spawn a dependency-mapper sub-agent before finalizing the graph:

```text
Agent(general-purpose, label="dependency mapper"):
  "Read the goal/task list and inspect the repo enough to map dependencies.
   Return STRICT JSON with task nodes, blocking_edges, soft_edges, waves,
   likely touched files/contracts, and a short rationale for each edge.
   Do not implement anything."
```

The orchestrator is the arbiter. It may revise the mapper output, but it must
document every override in the run ledger.

## Step 4 - Show The DAG Before Execution

Always pause and show the user:

- A wave table: which tasks run in each wave.
- Blocking edges: why a downstream task must wait.
- Soft edges: what seam obligations must be reviewed later.
- Checkpoints each task must produce before dependents can start.
- The machine-readable DAG stored in `.orchestrator/fleet.json`.

Do not spawn workers until the user approves the DAG.

## Step 5 - Persist The Run Ledger

Create `.orchestrator/fleet.json` before spawning workers. Treat it as the
source of orchestration state. `cmux read-screen` is evidence, not state.

Minimum ledger shape:

```json
{
  "run_id": "20260603-143000",
  "base_branch": "main",
  "tasks": [],
  "blocking_edges": [],
  "soft_edges": [],
  "waves": [],
  "seam_obligations": [],
  "checkpoints": []
}
```

Each checkpoint bundle must include:

- Producing task id and branch.
- Commit SHA.
- Produced contract/artifact.
- Review verdict.
- Verification evidence.
- Known limitations.

## Step 6 - Reapproval Rules

After approval, continue autonomously unless reality changes the graph.

Pause for renewed user approval when a worker discovers:

- A material API, schema, shared-component, data-model, auth, or UX-contract
  change.
- A new blocking dependency.
- A task that should be split.
- A risk-level increase that changes wave ordering or user-visible scope.

Normal implementation details do not require reapproval.

