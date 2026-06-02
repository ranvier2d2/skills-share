# Flashback Compatibility Matrix (Codex vs Claude)

Date: 2026-02-11

## Inputs and Evidence
- Codex skills root exists: `$CODEX_HOME/skills` or `~/.codex/skills`
- Claude skills root exists: `~/.claude/skills`
- Claude skill examples use slash invocation semantics: `~/.claude/skills/council/SKILL.md`
- Claude skills can invoke Codex scripts through an installed skill path: `~/.claude/skills/council/SKILL.md`
- Codex validation tool exists and runs: `$CODEX_HOME/skills/.system/skill-creator/scripts/quick_validate.py`

## Scoring Rubric
- `2` = full compatibility
- `1` = partial compatibility / adapter required
- `0` = blocker

## Matrix
| Dimension | Score | Evidence | Notes |
|---|---:|---|---|
| Memory discovery model compatibility | 2 | Both runtimes can discover filesystem-based `MEMORY.md` paths | Implemented shared discovery order + Claude fallback candidate |
| Tooling parity for read/edit/write operations | 2 | Both environments can execute shell/python operations | Runtime adapters isolate differences |
| Task list/TODO extraction parity | 1 | Claude has task-specific conventions; Codex uses generic file parsing | Standardized on markdown TODO parsing across runtimes |
| Clipboard behavior parity | 2 | Both run on same host, `pbcopy` callable from shell | Fallback warning when unavailable |
| Invocation semantics parity | 1 | Claude examples rely on slash-style invocation; Codex relies on natural-language skill trigger | Script interface normalizes runtime behavior |
| Safety constraints parity | 2 | Both runtimes can run non-destructive file workflow | Consolidation policy enforces no-delete/move-with-backlink |
| Validation workflow parity | 1 | `quick_validate.py` is Codex-side | Applied validator to both folders using shared script |
| Ongoing maintenance complexity | 2 | Shared core + thin runtime entrypoints keeps drift manageable | One script stack, two small SKILL.md wrappers |

**Earned points:** `13 / 16`

**Compatibility score:** `0.8125`

## Required Capability Blockers
Required dimensions:
- Memory discovery
- Safe updates
- Output generation

No required-capability dimension scored `0`.

## Decision
Dual-track implementation is approved.

Decision rule applied:
- Score >= 0.80: yes (`0.8125`)
- Required-capability blockers: none

Proceed with shared core + runtime adapters and dual skill entrypoints.
