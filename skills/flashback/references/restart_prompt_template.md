# Restart Prompt Template

Use this template to generate restart prompts. Fill all sections; omit `Locked Decisions` only when no decisions are available.

```markdown
I'm continuing work on [Project Name] ([version]).

Read your memory files to orient, then here's the session context:

## What Was Accomplished Last Session
- [outcome 1]
- [outcome 2]
- [outcome 3]

## Locked Decisions (Do Not Re-Litigate)
| Decision | Rationale | Date |
|----------|-----------|------|
| [decision] | [why] | [YYYY-MM-DD] |

## Active Tasks
| Task | Status | Next Action |
|------|--------|-------------|
| NNN: [name] | [status] | [specific next step] |

## Pending TODOs
- [todo]
- [todo]

## Immediate Next Action
[One executable next instruction]

## Files to Read First (in order)
1. `[path]` — [why]
2. `[path]` — [why]

## Warnings
- [uncommitted changes / blockers / caveats]

Don't start executing yet — read the referenced files first, then confirm your understanding before proceeding.
```

## Quality Gates
1. Every path in `Files to Read First` exists.
2. Immediate next action is specific and executable.
3. Prompt is self-contained for a fresh session.
4. Warnings include uncommitted changes when present.
