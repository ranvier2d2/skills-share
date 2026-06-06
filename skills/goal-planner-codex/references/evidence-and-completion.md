# Evidence And Completion

Use this reference when the Goal might otherwise be completed from weak,
stale, indirect, or merely plausible evidence.

## Verifiability Classification

Classify the user's intent before creating or completing a Goal.

- `verifiable`: final state and evidence are clear.
- `clarifiable`: likely final state exists, but success criteria are missing.
- `exploratory`: user wants discovery, research, or options.
- `unverifiable`: no responsible final state can be inferred yet.

Do not invent fake completion criteria for an unverifiable request. Recover the
definition first.

## Definition Recovery

Use this when the desired final state is fuzzy.

1. Sharpen fuzzy language.
   - Prefer canonical terms from available project docs, code, or user wording.
   - Ask whether overloaded terms mean distinct concepts.
2. Discuss concrete scenarios.
   - Invent edge cases that expose boundaries and dependencies.
3. Cross-reference code and docs.
   - If local evidence can answer the question, inspect it instead of asking.
   - Surface contradictions between user statements, code, glossary, and ADRs.
4. Propose verifiable success criteria.
   - Include the recommended final state and evidence source.
5. Ask only the next necessary question.
   - Provide a recommended answer and the tradeoff.

Do not edit `CONTEXT.md`, ADRs, or docs unless the user explicitly asks for
documentation updates.

## Discovery Goals

Allow discovery Goals when implementation-ready completion is not yet possible.

The completion artifact must be concrete, such as:

- clarified terminology,
- acceptance criteria,
- a decision memo,
- an options table,
- a prototype result,
- a prioritized candidate list,
- a next execution Goal proposal.

Weak:

```text
Improve the repo.
```

Better:

```text
Identify and prioritize three verifiable repo improvement candidates, with
evidence from code/docs and a recommended next implementation Goal.
```

## Evidence Plan

For each explicit requirement, name the evidence before completion.

Common evidence:

- changed files,
- command output,
- tests,
- build/typecheck output,
- screenshots or visual captures,
- API/runtime snapshots,
- PR or issue state,
- generated artifacts,
- user confirmation when human judgment is the actual acceptance signal.

Treat successful exits, ACKs, and file existence as limited evidence unless the
Goal's evidence policy says they are enough.

## Completion Audit

Before `update_goal(status="complete")`, produce a compact audit:

```text
Requirement -> evidence -> status
```

Statuses:

- `proved`: adequate current evidence exists.
- `weak`: some evidence exists, but it does not prove the requirement.
- `missing`: no adequate evidence exists.
- `contradicted`: evidence conflicts with the requirement.

Continue work unless every required item is `proved`.

After `update_goal` succeeds, report the final token/time usage returned by the
tool when available.
