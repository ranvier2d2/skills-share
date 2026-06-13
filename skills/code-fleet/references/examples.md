# Examples

## Multi-Task Feature Build

```text
User: "Orchestrate these 4 tasks across the fleet: <list>"
-> RunTaskFleet
-> Dependency mapper builds a DAG
-> User approves the wave plan
-> Assessor sub-agents score each task L1-L4
-> Orchestrator sizes the ready set, then calls the Workflow tool once for the wave
   (wave-runner.js runs Phases 1-5: work -> review -> fix -> verify per task)
-> Orchestrator integrates each green wave (writes the ledger, git merge --no-ff)
-> Dependents branch from the latest integration branch
-> FinalMerge creates a release branch, runs global seam review, opens PR
```

## Worker Ambiguity

```text
Worker: "Unclear whether to use the existing AuthService or add a new one."
-> Orchestrator spawns Agent(general-purpose):
   "Find how auth is wired in this codebase, report the convention and best choice."
-> Agent returns: "Reuse AuthService; it is the single entry point in src/auth."
-> Worker proceeds and notes the assumption in its commit.
```

## Final Merge

```text
User: "Everything's done - merge it."
-> FinalMerge (the agent does it directly — no separate merge instance)
-> Starts from integration/<run-id>/wave-<last>, creates release/<goal-slug>
-> Checks unresolved seams against the ledger
-> Runs a Claude merge-seam review panel (C/CM/P, cross-wave focus)
-> Dispositions ACCEPT / FIX_LATER / DEFER
-> Opens PR
-> Runs /review <PR#>
```
