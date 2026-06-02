# Key Moment Selection

A key moment is a timestamp or window that changes the answer.

## Signals

Visual change:
- scene cut, window change, modal opens/closes, navigation, selection changes
- empty state appears, error appears, loading completes
- cursor action, drag, click target, form submission

Textual change:
- labels, page titles, search terms, counts, status text, errors
- visible before/after values

Audio change:
- speaker change, explicit claim, hesitation, correction, named object
- silence after action when it changes interpretation

Question relevance:
- moments that directly confirm, disconfirm, or explain the user's question

Uncertainty reduction:
- moments likely to resolve a contradiction or weak inference

## Ranking

Prefer moments that are:

1. Relevant to the user question.
2. Evidence-backed and timestamped.
3. Semantically different from already selected moments.
4. Close to observed state transitions.
5. Useful for deciding the next inspection pass.

For long videos, rank per segment first, then merge with diversity so one
repetitive section does not consume the whole budget.

## Anti-Patterns

- Selecting visually dramatic but irrelevant motion.
- Treating a static empty state as nothing.
- Keeping only evenly spaced frames when the action is clustered.
- Summarizing a video without evidence pointers.
