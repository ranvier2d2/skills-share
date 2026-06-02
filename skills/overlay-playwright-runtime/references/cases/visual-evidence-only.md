# Case: Capture Visual Evidence Only

Use this case when:

- the user wants screenshots or reviewable evidence more than a full audit
- the agent needs visual proof while iterating
- a full report bundle would be unnecessary overhead

Implementation mode:

- `operate`

Primary helper:

- `captureVisualEvidence(...)`

Also read:

- [../interactive.md](../interactive.md)

## User-facing phrasing

Prefer:

- `Capture visual evidence only`

## Capture modes

Use:

- `viewport` for the current visible state only
- `full-page` for one stitched capture
- `scroll-slices` for long surfaces that need multiple reviewable screens

## Default guidance

Prefer `scroll-slices` when:

- the page is taller than one viewport
- the user needs visual review completeness
- the evidence may be used in a report later

Prefer `viewport` when:

- the user only wants the current visible state
- you are proving a very local change

Prefer `full-page` when:

- the page stitches cleanly
- one long image is genuinely easier to review than multiple slices
