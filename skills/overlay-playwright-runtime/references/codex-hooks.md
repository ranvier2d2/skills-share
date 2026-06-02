# Codex Hooks Integration

Use this reference when a repo wants Codex to notice overlay annotation previews
without the agent hunting for artifacts manually.

## What The Hook Does

The skill-level review flow remains the source of truth:

- `previewPlannedAnnotation(...)` writes the raw screenshot, preview HTML,
  flat preview image, and preview JSON.
- `reviewPlannedAnnotation(...)` writes the review descriptor with
  `requiresVisualReview`, `confidence`, `suggestedNextAction`, and
  `inspectionTargetPath`.

When `requiresVisualReview` is true and the current repo has a `.codex/`
directory, the sandbox helper appends a queue entry to:

```text
.codex/state/overlay-review-queue.jsonl
```

The repo-local `PostToolUse` hook reads that queue after Bash commands and
returns a Codex message that names the exact flat image to inspect.

## Repo Setup

Enable lifecycle hooks in `.codex/config.toml`:

```toml
[features]
codex_hooks = true
```

Register the hook in `.codex/hooks.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "node \"$(git rev-parse --show-toplevel)/.codex/hooks/overlay-review-hook.mjs\"",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Keep hook runtime state out of git:

```gitignore
.codex/state/
```

## Agent Behavior

Treat the hook message as a required next step for the current turn:

- Open `inspectionTargetPath` with the local image viewer.
- Accept the plan only when the note, arrow, and target are clear.
- Retry or reflow placement when the note blocks the target or nearby controls.
- Downgrade to a safer renderer when the frame is crowded.

The hook does not perform visual reasoning. It orients the agent toward the
artifact that needs multimodal inspection.

## Operational Notes

- `CODEX_OVERLAY_REVIEW_QUEUE_PATH=/absolute/path.jsonl` overrides the queue.
- `CODEX_OVERLAY_REVIEW_QUEUE_PATH=0` disables queue writes from the sandbox
  helper for test runs.
- The hook ignores queue entries whose descriptor or inspection image no longer
  exists.
- A `Stop` hook can be added later if we need to prevent a turn from ending
  while required visual reviews are still pending.
