# Annotation style

## Purpose

Produce review artifacts that are fast to scan and easy to discuss asynchronously.

## Rules

### One finding per callout

Do not combine multiple defects into one note.

### Keep notes short

Target one sentence fragment, not a paragraph.

Good:
- `Spacing feels tight here`
- `Primary action is visually buried`
- `Table header wraps unexpectedly`

Bad:
- `This section has a number of spacing issues and also the contrast feels weak and the alignment is probably off`

### Point at the exact target

Put the arrow tip on the exact UI element or boundary that matters.

### Keep notes nearby

Place the note close enough that the association is obvious, but not on top of the important UI.

### Prefer edge placement

When possible, place notes in side gutters or empty whitespace and point inward.

### Avoid clutter

If more than five callouts are needed, split the review into multiple images.

### Use stable language

Describe what is visible. Avoid guessing implementation causes unless the user asked for that.

Good:
- `Footer links are too close together`
- `Selected state is hard to distinguish`

Bad:
- `Probably a flexbox bug here`

### Match text to audience

For PRs and engineering issues, use direct defect language.

For stakeholder reviews, soften wording and make the action clearer.

## Suggested review sequence

1. Critical blockers
2. Layout and hierarchy issues
3. Interaction clarity issues
4. Cosmetic polish
