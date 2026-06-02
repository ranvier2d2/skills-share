# Workflow Rules

## Record the demo when

- A reviewer would reasonably ask, "what does the UI look like now?"
- The issue changes user-visible behavior.
- A handoff would benefit from visual proof rather than only text.

## Skip the demo when

- The change is backend-only.
- The output is not visual.
- The UI is unchanged and only internal implementation moved.

## Keep the demo high signal

- Show only the flow that proves the change.
- Start from a clean app state when practical.
- Avoid unrelated tabs, windows, or secrets.
- Favor one short successful path over a long exploratory video.

## Minimum proof standard

A good demo should answer:
- What changed?
- Where is it visible?
- Does the target flow now work?

## Publication rule

Use a Linear attachment plus a short issue comment.
Do not rely on a vague "see video" message with no summary.
