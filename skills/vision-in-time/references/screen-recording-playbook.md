# Screen Recording Playbook

Screen recordings are the v1 center of gravity for this skill.

## Inspect For

- app or page identity
- navigation path
- search terms and filters
- clicks, cursor movement, selections
- loading, empty states, errors, modals
- before/after values
- moments where the user expected something but the UI did not produce it

## Workflow

1. Probe video.
2. Sample sparse frames.
3. Build contact sheet.
4. Identify screen states.
5. Identify transitions between states.
6. Materialize frames around transitions.
7. Answer with timestamps and uncertainty.

## Domain Object Model

For UI videos, model frames as:

- view/screen
- controls
- user action
- visible data
- state transition
- error or empty state
- implied task

The functional pipeline extracts evidence. The object model interprets what the
evidence contains.
