# Bounded Memory

Video can overwhelm context, RAM, and disk. Use a staged strategy.

## Levels

Naive:
- Extract many frames.
- Inspect directly.
- Useful only for short clips.

Sparse evidence:
- Probe metadata.
- Sample frames every N seconds.
- Build a contact sheet.
- Inspect only likely windows.

Pointer-first:
- Keep timestamps and paths in an evidence index.
- Materialize frames or clips only when needed.
- Use reinspection around uncertainty.

Delegated:
- Split long video into evidence windows.
- Child Agents inspect windows and return compressed observations.
- Root Agent merges and verifies.

Streaming:
- Maintain a rolling belief state and discard low-value raw frames.
- Persist only evidence pointers, selected frames, summaries, and uncertainties.

## Storage Rules

- Put outputs in a user workspace folder such as `vision-in-time-output/`.
- Do not write outputs inside the skill directory.
- Prefer JPEG frames and short clips over full decoded video.
- Clean caches after the user confirms they are no longer needed.

## RAM Rules

- Never load all frames into memory.
- Process one frame/window at a time.
- Use manifests and JSONL when evidence grows large.
