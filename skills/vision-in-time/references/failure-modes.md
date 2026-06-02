# Failure Modes

## No Audio

Do not assume missing audio is failure. Switch to visual state transitions,
visible text, cursor movement, and screen object modeling.

## Audio Without Useful Video

Use transcript/timestamps as the primary evidence and sample frames around
spoken references.

## Tiny Text

Increase frame resolution, inspect original frames, or materialize short clips.
Avoid relying on OCR when visual inspection can read state better.

## Long Video

Split into windows. Use Child Agents when the root context would be flooded.
Merge compressed observations.

## Repetitive UI

Select diverse states, not merely equal intervals. Empty states, failed
searches, and filter changes matter.

## Bad Timestamps

Rebuild metadata from `ffprobe`, validate duration, and prefer seconds as the
canonical internal representation.

## Missing Tools

If `ffmpeg` or `ffprobe` is missing, explain the blocker and provide the
expected command. Do not pretend the video was inspected.

## Feedback Ignored

If the user says a moment was missed, convert that feedback into a specific
reinspection target.
