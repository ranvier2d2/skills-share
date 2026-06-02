# ChordChemist CLI Contract

All commands run from the ChordChemist repository:

```bash
npm run --silent cc -- <domain> <action> [flags]
```

Every response is JSON:

```json
{
  "ok": true,
  "command": "melody.generate",
  "result": {},
  "warnings": [],
  "nextSuggestedCommands": []
}
```

Failures also return JSON and exit non-zero:

```json
{
  "ok": false,
  "command": "key.detect",
  "error": "key detect requires --bins or --pitch-classes",
  "warnings": []
}
```

## Global Flags

- `--compact`: minify JSON output.
- `--state <file|->`: read a JSON state object. Use `-` for stdin.
- `--input <file|->`: alias for `--state`.

State objects may contain:

```json
{
  "tonic": "D",
  "mode": "minor",
  "degrees": [1, 6, 3, 7],
  "progression": [],
  "melody": {},
  "canvas": {},
  "range": { "low": 57, "high": 76 },
  "vocalRange": { "low": 57, "high": 76 }
}
```

## Commands

### Theory

```bash
npm run --silent cc -- theory key --tonic C --mode major
```

Returns the seven diatonic seventh chords with degree, symbol, roman numeral, harmonic function, and notes.

### Circle of Fifths

```bash
npm run --silent cc -- circle relation --from C --to F#
npm run --silent cc -- circle transpose --tonic C --steps -1
```

Use this for tonal distance, modulation direction, or "closer/farther from home" reasoning.

### Progressions

```bash
npm run --silent cc -- progression render --tonic A --mode minor --degrees 1,6,3,7
npm run --silent cc -- progression suggest --tonic C --mode major --current-degree 5
```

`render` resolves scale degrees into ChordChemist chord objects. `suggest` returns theory-aware next-chord candidates.

### Melody

```bash
npm run --silent cc -- melody generate --tonic D --mode minor --degrees 1,6,3,7 --bars 4 --seed 42
npm run --silent cc -- melody analyze --state song.json
npm run --silent cc -- melody edit --state song.json --scope phrase:phrase-2 --operation resolve-tensions
npm run --silent cc -- visual piano-roll --state song.json --out output/piano-roll.svg
```

Generation returns a raw melody, a summary, and a compact Melody Canvas. Analysis returns a full canvas and compact digest. Editing returns an updated melody, compact canvas, touched note ids, and a `changed` flag.

Useful generation flags:

- `--bpm <40..220>`
- `--bars <1..16>`
- `--density sparse|medium|busy`
- `--contour ascending|descending|arch|wave|random`
- `--rhythm straight|syncopated|swing`
- `--octave <3..6>`
- `--seed <integer>`

Edit scopes:

- `--scope all`
- `--scope bar:2`
- `--scope phrase:phrase-1`
- `--scope motif:motif-1`
- `--scope notes:melody-42-1+melody-42-2`

Edit operations:

- `regenerate`
- `make-more-stepwise`
- `increase-leapiness`
- `resolve-tensions`
- `simplify-rhythm`
- `add-space`
- `transpose-motif`
- `sequence-motif`
- `set-ending`
- `set-note`

### Visuals

```bash
npm run --silent cc -- visual piano-roll --state song.json --out output/piano-roll.svg
```

`visual piano-roll` writes a deterministic SVG piano-roll view from the Melody Canvas. It uses real note timing, MIDI pitch, chord labels, section bands, chord-tone/tension coloring, tonic landing highlights, and any `arrangement.*.notes` counterpoint metadata present in the state.

Useful render flags:

- `--out <file.svg>`
- `--title <text>`
- `--min-note <note>` and `--max-note <note>`
- `--sections <Label:1-4,Other:5-8>`; use underscores for spaces if needed.

### Audio

```bash
npm run --silent cc -- audio render --state song.json --out output/demo.wav
npm run --silent cc -- audio render --tonic C# --mode minor --degrees 1,5,1 --bpm 168 --bars 3 --density busy --out output/demo.wav
```

`audio render` writes a deterministic local WAV preview that can be played on macOS with `afplay`.

Useful render flags:

- `--out <file.wav>`
- `--play`: render and immediately play with macOS `afplay`.
- `--melody-only`
- `--chords-only`
- `--no-melody`
- `--no-chords`
- `--no-bass`
- `--sample-rate <8000..96000>`
- `--tail-seconds <number>`
- `--beats-per-chord <number>`
- `--voicing-style close|open|drop2|shell|rootless`
- `--voicing-octave <integer>`
- `--inversion <integer>`

Returns the output path, WAV metadata, rendered part counts, and an `afplay` command in `nextSuggestedCommands`.

### Vocal Adaptation

```bash
npm run --silent cc -- vocal adapt --tonic C --mode major --degrees 1,5,6,4 --range-low 57 --range-high 76
```

Returns ranked key candidates that preserve the mode and scale-degree progression while improving vocal comfort.

### Key Detection

```bash
npm run --silent cc -- key detect --pitch-classes C:900,E:700,G:850,A:450
npm run --silent cc -- key detect --bins 900,0,300,0,700,0,0,850,0,450,0,0
```

Pitch-class entries are `pitch:durationMs[:clarity]`. Pitch can be a note name (`C#`) or chroma number (`1`).
