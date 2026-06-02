# Transit 2 Workflow Notes

Date captured: 2026-05-30

## Agent decision order

When asked to use Transit 2 in an Ableton production session:

1. Identify the musical role first: transition, pad movement, rhythmic motion,
   sidechain texture, or special effect.
2. Prefer individual tracks or transition buses before master/main bus use.
3. Inspect visible preset and exposed Ableton parameters.
4. Record safe macro points before proposing automation curves.
5. Generate a plan-only automation artifact before writing any lane.
6. Require producer listening acceptance before marking the movement as
   musically accepted.

## Ableton bridge notes

Known current target:

```text
Track index: 6
Track name: Atmos Pad - Song Glue
Device index: 1
Device name: Transit 2
Parameter index: 1
Parameter name: 1. MACRO CONTROL
```

Use readback before assuming the current Live Set still matches this target:

```bash
uv run python scripts/ableton_state_cli.py --json get /live/device/get/parameters/name 6 1
uv run python scripts/ableton_state_cli.py --json get /live/device/get/parameters/value 6 1
```

Preview parameter writes with:

```bash
uv run python scripts/ableton_state_cli.py set-param 6 1 1 0.2 --dry-run --json
```

Generate a plan-only curve artifact with:

```bash
uv run python scripts/automation_curve_plan.py create \
  --section-name "hook transition" \
  --intention "small late Transit 2 lift on the Atmos Pad into the next downbeat without breaking listener continuity" \
  --avoid "full macro sweep" \
  --avoid "master-bus style transition" \
  --start-bar 16 \
  --end-bar 16 \
  --out outputs/audio-sketch-materialization/device-macro-automation/transit2-atmos-pad-small-late-lift-plan.json \
  --json
```

## Safe-point table

| Scope | Value | Meaning | Status |
| --- | ---: | --- | --- |
| Baseline | 0.1320969164 | Resting value heard in current preset | observed |
| Safe expressive point | 0.20 | On-time delay/filter color, lift without disruption | producer accepted |

## Current caveats

- AbletonOSC can set plugin parameters but may not acknowledge write commands;
  use fire-and-verify patterns.
- Computer Use may be needed to inspect the native plugin window or configure
  exposed parameters.
- Transit 2 presets can expose very different behavior under the same macro
  value; safe points are preset-specific.
- Do not assume the current `A Meta Filter` reference applies to another
  preset.

## Future research branches

- Compare Macro, Follower, and Sidechain modes on the same musical phrase.
- Capture at least one edge/risk point above 0.20 for `A Meta Filter`.
- Decide whether arrangement-lane writing should happen through Computer Use,
  Max for Live bridge support, or a hybrid plan/write/verify loop.
- Create a tiny preset audition checklist for Transit 2 inside Ableton.
