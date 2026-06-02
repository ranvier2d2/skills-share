# Evidence Model

## Core Objects

`Video`
: Source media plus metadata: path, duration, frame rate, dimensions, streams,
and probe time.

`Frame`
: A materialized still image at one timestamp.

`EvidencePointer`
: A lightweight reference to evidence without loading it into context.

```json
{
  "id": "ev_001",
  "type": "frame",
  "source": "video.mp4",
  "t_start": 12.34,
  "t_end": 12.34,
  "path": "frames/frame_000012.jpg",
  "reason": "first visible empty inbox result"
}
```

`EvidenceWindow`
: A bounded time span worth inspecting or delegating.

`CandidateMoment`
: A suspected meaningful moment before final ranking.

`KeyMoment`
: A selected moment that affects the answer.

`Timeline`
: Ordered observations anchored to timestamps and evidence ids.

`UncertaintyReport`
: What could not be read, aligned, heard, verified, or inferred.

`FeedbackChannel`
: Optional input from prior output, such as "missed the filter step" or "look
for inbox search failure."

## Minimal Index

An `evidence-index.json` should contain:

- `video`: metadata and source path.
- `frames`: sampled frame pointers.
- `candidate_moments`: ranked moments to inspect.
- `observations`: timestamped claims.
- `uncertainties`: unresolved limits.
- `feedback`: optional prior feedback used in this pass.

Do not store raw image data in JSON. Store paths and timestamps.
