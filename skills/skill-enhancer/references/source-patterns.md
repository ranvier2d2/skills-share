# Source Patterns

Use this reference when the user asks for source-backed skill enhancement, comparative analysis, or a port from Claude skills to Codex skills.

## Pattern Matrix

| Source | Reusable pattern | Apply when |
| --- | --- | --- |
| Matt Pocock `grill-me` | Walk the design tree, ask one question at a time, include a recommended answer, and inspect the codebase instead of asking when evidence is local. | A skill's behavior depends on unresolved product, architecture, or workflow choices. |
| Matt Pocock `grill-with-docs` | Check domain docs, glossary, ADRs, and code examples; challenge fuzzy language and contradictions. | A skill must align with a codebase or operational vocabulary. |
| Matt Pocock `write-a-skill` | Gather requirements, draft the skill, review triggers, split references, add scripts for deterministic repeated work. | Creating a new skill or turning a one-off prompt into reusable procedure. |
| Superpowers `writing-skills` | Treat skills as testable process documentation; use RED/GREEN/REFACTOR thinking and pressure scenarios. | The skill is meant to improve agent behavior, not just store facts. |
| Superpowers `testing-skills-with-subagents` | Baseline failure, minimal skill, pressure-test with realistic prompts, capture rationalizations and loopholes. | The skill should prevent common agent failure modes. |
| Superpowers `verification-before-completion` | Identify checks, run them, read output, and only then claim completion. | Any skill can produce false confidence or skip validation. |
| Superpowers `using-skills` | Read the skill before applying it; create todos when the skill provides a checklist. | The current task explicitly invokes a skill or a workflow skill has multiple required steps. |
| Project-local Claude skills | Phase-based workflows, explicit arguments, context-loading passes, dry-run safety, domain rules, and confirmation checkpoints. | Porting project-specific Claude skills or designing skills for operational repositories. |
| Codex `skill-creator` | Required `SKILL.md`, recommended `agents/openai.yaml`, concise trigger description, progressive disclosure, no extraneous docs, validator-first finish. | Building or updating local Codex skills. |

## Local Source Locations

- User Codex skills: `$CODEX_HOME/skills` or `~/.codex/skills`
- User Claude folder: `~/.claude`
- Project-local Claude skills: `<project-root>/.claude/skills`
- Matt Pocock skills clone used for V1 research: `/tmp/mattpocock-skills`
- Superpowers skills clone used for V1 research: `/tmp/superpowers-skills`

## Enhancement Heuristics

### Trigger Design

The frontmatter description is the discovery surface. It should answer:

- What capability does this skill add?
- What exact requests should trigger it?
- What artifacts or file types does it work on?
- What adjacent requests should not trigger it?

Prefer active phrases such as "Use when creating...", "Use when reviewing...", and "Use when porting..." over broad labels like "helps with skills."

### Progressive Disclosure

Keep `SKILL.md` short enough to be read every time. Move details into references when they are:

- Comparative source notes.
- Long examples.
- Domain-specific rules.
- Provider or framework variants.
- Rare troubleshooting paths.

Keep references one level away from `SKILL.md`; avoid chains of references that require hunting.

### Questioning Protocol

Ask when a decision changes the implementation. Do not ask when the answer can be found locally.

Good question shape:

1. State the unresolved decision.
2. Offer the recommended answer.
3. Name the tradeoff.
4. Ask for confirmation or correction.

Stop asking when the next edit is clear enough to execute responsibly.

### Pressure Testing

Use one or more realistic prompts that would previously fail. Check whether the skill:

- Triggers for the right task.
- Avoids over-asking.
- Loads references only when useful.
- Produces a concrete edit or review.
- Validates before completion.
- Reports assumptions and residual risk.

### Porting Claude Skills To Codex

Translate platform-specific features instead of copying them blindly:

- Claude frontmatter fields become Codex frontmatter plus optional `agents/openai.yaml`.
- Claude slash-command arguments become ordinary workflow inputs or examples.
- Claude allowed-tools should become tool preferences or safety notes.
- Project-specific rules should stay in project instructions unless the technique is reusable.
- Long procedural or domain material should move into `references/`.

## Completion Checklist

- `SKILL.md` has no unfinished scaffold text.
- Frontmatter description is specific enough for discovery.
- `agents/openai.yaml` is present for Codex skills and the default prompt mentions `$skill-name`.
- Relative links in `SKILL.md` point to real files.
- No extra README, changelog, or implementation diary was added.
- Validation was run or the reason it could not be run is reported.
