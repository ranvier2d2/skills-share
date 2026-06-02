# Consolidation Policy

## Goal
Keep `MEMORY.md` concise while preserving all durable context.

## Budget
- Warning threshold: `180` lines
- Hard limit target: `< 200` lines

## Protected Sections (Never Auto-Move)
If section title contains any of:
- `invariant`
- `safety`
- `architecture`
- `architecture map`

## Movable Sections (Allowlist)
Only these section families can be moved when `MEMORY.md > 180`:
- `task history` -> `task_history.md`
- `session notes` -> `session_notes.md`
- `working notes` -> `working_notes.md`
- `execution log` -> `execution_log.md`
- `findings` -> `findings.md`
- `scratchpad` -> `scratchpad.md`
- `observations` -> `observations.md`

## Move Rules
1. Move only one largest allowlisted section per run.
2. Never delete information.
3. Replace moved section body with one-line backlink.
4. In moved file, append import timestamp and preserved section content.
5. Add moved file to `Quick Links` when present.

## Checkpoint Rules
- Always append/update `## Flashback Checkpoints` in `MEMORY.md`.
- Always use timestamped output filenames.
- Never overwrite prior flashback output files.

## Failure Handling
- If no allowlisted section is available and memory is over budget, warn and proceed.
- Clipboard failures are warning-only.
- In dry-run mode, do not mutate files.
