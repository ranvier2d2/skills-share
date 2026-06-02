# Transit 2 Reference

Date captured: 2026-05-30
Skill: `ableton-live-m4l-codex`

## Purpose

This folder stores reference material for using Baby Audio Transit 2, made in
collaboration with Andrew Huang, inside the Ableton + Max for Live + Codex
workflow.

Use this reference when the producer asks for motion effects, transition color,
macro automation, sidechain-driven movement, or Transit 2 preset exploration.

## What Transit 2 is for in this skill

Transit 2 is best treated as a motion-enabled multi-effect, not as a mastering
default. In this workflow, it belongs first on an individual musical layer or
transition bus where the producer can hear whether the motion supports the song.

Good first uses:

- subtle pad movement,
- late-phrase lift,
- transition color,
- rhythmic motion on static parts,
- sidechain-derived movement that follows drums or another source.

Use with care on:

- the master/main bus,
- full macro sweeps,
- destructive resampling,
- heavy glitch or stutter effects before the arrangement is stable.

## Confirmed local reference case

```text
Live Set: devin.als
Track: Atmos Pad - Song Glue
Device: Transit 2
Visible preset: A Meta Filter
AbletonOSC target: track 6, device 1, parameter 1
Parameter exposed to Live: 1. MACRO CONTROL
Baseline: 0.1320969164
Producer-accepted safe point: 0.20
Musical meaning: timed-delay/filter motion that adds lift without breaking listener continuity
Preferred first curve shape: small_late_lift
```

Visible modules in the preset window:

```text
Distortion -> Filter 12 -> OTT -> Bitcrusher -> Flanger -> Delay -> Analog Chorus
```

The corresponding workspace artifacts are:

```text
docs/device-macro-automation-practice.md
docs/device-macro-safe-points.manifest.json
schemas/device-macro-safe-points.v1.schema.json
schemas/automation-curve-plan.v1.schema.json
scripts/automation_curve_plan.py
outputs/audio-sketch-materialization/device-macro-automation/transit2-atmos-pad-small-late-lift-plan.json
```

## Operating rule

Do not jump from "the parameter can be written" to "the automation is accepted."

For this skill, accepted Transit 2 automation requires:

1. a structured plan,
2. RuntimeState readback or UI inspection,
3. producer listening acceptance.

Until at least three heard points exist for a parameter, prefer safe points over
curves.

## Motion mode map

- `Macro`: first choice for this skill because Live can expose the macro as a
  device parameter and the agent can plan safe points before writing lanes.
- `LFO`: useful for host-synced movement on static pads, guitars, or pianos.
- `Follower`: useful when Transit 2 should react to the current track's
  dynamics.
- `Sidechain`: useful when movement should follow another signal, such as kick
  or drums.
- `Gate`: useful for live/performance-triggered transitions.
- `Sequencer`: useful for DAW-grid aligned transitions and click-triggered
  sections.

## Current risk notes

- Overuse can make the arrangement sound like a preset demo rather than a song.
- Full macro sweeps are not assumed safe; capture safe points first.
- Sidechain and follower behavior changes when source dynamics change.
- Delay/reverb tails can help continuity or smear loop boundaries; listen in
  context.
- Pitch, warp, loop, reverser, bitcrush, OTT, and heavy feedback settings need
  explicit listening checks before automation.
- Some modules can introduce latency or live-performance friction; treat Pitch+
  and preset switching as risk points until tested in the current set.

## Recommended v1 shape

For the current reference case:

```text
small_late_lift:
- stay near baseline at the phrase start,
- rise briefly to 0.20 late in the phrase,
- return to baseline before the next downbeat.
```

This matches the producer note that the 0.20 value feels like an on-time delay
and does not disrupt continuity.

## Files in this folder

- `README.md`: how to use Transit 2 inside this skill.
- `sources.md`: source-backed facts and links.
- `sources-and-gaps.md`: independent gap analysis and README recommendations.
- `workflow-notes.md`: practical operating notes for Codex agents.
