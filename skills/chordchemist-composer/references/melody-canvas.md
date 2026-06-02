# Melody Canvas Reference

Melody Canvas is ChordChemist's semantic piano-roll layer. It converts raw generated notes into musically meaningful edit handles so an agent can reason about melody in context.

## Core Concepts

- Raw melody notes carry `note`, `startBeat`, `durationBeats`, and `velocity`.
- Canvas notes add `id`, `midi`, `pitchClass`, `bar`, `beatInBar`, chord context, scale degree, chord relation, tension role, contour role, phrase role, and optional motif id.
- Phrases group note ids over beat ranges.
- Motifs group repeated interval/rhythm signatures.
- Summary fields are safe to pass into prompts.

## Note Fields to Use

- `id`: stable target for note-scoped edits.
- `bar` and `beatInBar`: human-oriented location.
- `overChordRoman`: harmonic context.
- `scaleDegree`: active key/mode degree, or `null` if outside.
- `chordRelation`: `root`, `third`, `fifth`, `seventh`, `extension`, `non-chord-tone`, `outside`, or `unknown`.
- `tensionRole`: `stable`, `passing`, `neighbor`, `approach`, `suspension`, `anticipation`, `appoggiatura`, `escape`, `chromatic`, or `unknown`.
- `contourRole`: `start`, `peak`, `valley`, `arrival`, `tail`, or `inner`.
- `chordRootCircleRelation`: Circle-of-Fifths relation from the active key tonic to the underlying chord root.

## Agent Pattern

1. Generate or load a melody.
2. Analyze it:

```bash
npm run --silent cc -- melody analyze --state song.json --compact
```

3. Inspect `result.compact.summary`, `phrases`, `motifs`, and `notes`.
4. Choose a scope and operation:

```bash
npm run --silent cc -- melody edit --state song.json --scope phrase:phrase-2 --operation resolve-tensions --target-scale-degree 1
```

5. If `changed:true`, use the returned `melody` and `canvas` as the new working state. If `changed:false`, report that the selected scope already satisfied the requested transform or did not match editable notes.

## Melody Audition Loop

The app keeps Copilot melody changes reversible:

- `suggest_melody` and `edit_melody` apply the after-state immediately.
- The melody store keeps a pending `audition` with `before`, `after`, request metadata, touched note ids, and compact summaries.
- Use `play_melody_audition` for before/after comparisons.
- Use `accept_melody_audition` when the user says to keep it.
- Use `revert_melody_audition` when the user says to undo, go back, or restore the previous melody.

For users, this should feel like manipulating an audible piano roll: hear before, hear after, accept, or revert.

## Feedback-Gated Development

For longer composition work, do not expand every promising fragment automatically. After rendering or editing a candidate, ask the user to choose the material to develop when the choice affects identity:

- motif selection: which gesture should become the theme.
- articulation: staccato, legato, sparse, or busier.
- section role: verse/theme, hook, bridge, contrast, cadence, outro.
- direction: accept, revert, simplify, intensify, or extend.

When `request_user_input` is callable in the active tools, call it for concise mutually exclusive choices instead of writing a plain-text menu. Put the recommended musical direction first. If unavailable, ask the same question in plain text and continue only after the user answers or explicitly delegates the choice.

## Musical Interpretation Hints

- High `chordToneRatio` means the melody is harmonically anchored.
- High `averageLeapSemitones` means less stepwise/cantabile.
- `finalScaleDegree` and `finalChordRelation` indicate cadence strength.
- `averageChordRootFifthsDistance` and `farthestChordRootCircleRelation` indicate harmonic distance from the home key.
- For "more resolved", target final notes with `scaleDegree` 1, 3, or 5 and chord relations `root`, `third`, or `fifth`.
- For "more suspended", preserve non-chord tones longer or avoid final root/fifth arrivals.
- For "keep the hook", use motif scope instead of regenerating the full melody.
