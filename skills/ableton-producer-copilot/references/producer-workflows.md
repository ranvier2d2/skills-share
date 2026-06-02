# Producer Workflows

## Vibe To Song Seed

Use when the user says things like:

- “quiero algo oscuro pero bailable”
- “make a melancholic progression in D minor”
- “hagamos un hook estilo nocturno”
- “tengo esta letra, qué acordes le quedan”

Output:

1. **Tempo lane**: slow, mid, or club range.
2. **Key/mode**: tonic and mode with emotional reason.
3. **Progression**: 4-8 chords with roman numerals and chord names.
4. **Hook contour**: shape, register, and rhythmic feel.
5. **Ableton move**: what to send or audition first.

Default if unclear:

```text
Minor key, 82-96 BPM, 4-bar loop, one strong color chord, sparse hook.
```

## Harmony Decisions

Producer levers:

- **Darker**: more minor iv, bVI, bVII, borrowed chords, lower voicing.
- **Brighter**: relative major lift, IV/VI emphasis, add9/maj7 color.
- **More tension**: secondary dominants, sus chords, delayed resolution.
- **More loopable**: avoid full cadences, end on V, bVII, or a suspended tonic.
- **More singable**: slower harmonic rhythm, fewer chromatic shifts, clearer tonic returns.

Useful response:

```text
I’d keep the loop unresolved: i - bVI - bIII - bVII.
That gives you sadness without killing momentum. If the vocal needs more lift, swap bar 4 to V7 before the hook.
```

## Melody And Hook

Think in contour before notes:

- **Intimate verse**: narrow range, stepwise, late downbeat entries.
- **Hook**: repeated motif, one memorable leap, stronger rhythmic identity.
- **Pre-chorus**: rising contour, shorter notes, unresolved ending.
- **Bridge**: register shift, fewer repeated tones, contrasting rhythm.

Ask for feedback only after proposing a contour:

```text
Should the hook be: low and hypnotic, rising and emotional, or punchy and rhythmic?
```

If `request_user_input` is callable, ask it this way:

```text
question: "Which hook contour should I develop?"
options:
- label: "Low hypnotic (Recommended)"
  description: "Keeps the vocal intimate, darker, and easy to loop."
- label: "Rising emotional"
  description: "Creates a bigger lift into the hook or chorus."
- label: "Punchy rhythmic"
  description: "Makes the melody more beat-driven and memorable."
```

For vocal adaptation, prefer `$chordchemist-composer` so range/key choices are grounded.

## Arrangement Map

Default pop/electronic map:

```text
Intro: 4-8 bars, filtered or sparse motif
Verse: 8-16 bars, low density
Pre: 4-8 bars, harmonic or rhythmic lift
Hook: 8-16 bars, full motif and bass
Break: 4-8 bars, contrast or vocal space
Hook 2: bigger variation
Outro: subtractive exit
```

Ableton translation:

- Use Session View scenes for section auditions.
- Keep chord, melody, bass, and counter-melody as separate clips when comparing.
- Use “before/after” neighboring clip slots for risky melody edits.

## Production Moves

Use musical intent, not plugin shopping.

Common directions:

- **More expensive**: fewer parts, better register separation, subtle automation, longer tails.
- **More intimate**: dry vocal/piano/synth close-up, less top-end sparkle, smaller room.
- **More club**: simpler harmony, stronger bass root movement, tighter transient contrast.
- **More cinematic**: slower harmonic rhythm, pedal tones, swells, octave doubling.
- **More demo-to-record**: commit to one lead motif, remove duplicate layers, automate transitions.

Ableton-specific suggestions:

- Put the M4L bridge before the instrument.
- Use E-Piano or a simple synth for harmonic audition before sound-designing.
- Write chords first, then bass roots, then hook melody.
- Do not overproduce before the loop survives repeated listening.

When the user asks to send an idea to Ableton, create a `LiveBridgeClip` JSON and call the bundled bridge script. Minimal clip shape:

```json
{
  "name": "Verse dark loop",
  "lengthBeats": 16,
  "notes": [
    { "pitch": 60, "startTime": 0, "duration": 3.95, "velocity": 90 },
    { "pitch": 64, "startTime": 0, "duration": 3.95, "velocity": 90 },
    { "pitch": 67, "startTime": 0, "duration": 3.95, "velocity": 90 }
  ]
}
```

Command:

```bash
scripts/live-bridge.mjs write ./clip.json --replace --dry-run
scripts/live-bridge.mjs write ./clip.json --replace
```

After writing, use `fire` only when the user wants Live playback.

When the user asks to revise material that already exists in Ableton, read the real target first. Use explicit targets when possible:

```bash
scripts/live-bridge.mjs read
scripts/live-bridge.mjs read --target=session_clip_slot --track=0 --scene=2
scripts/live-bridge.mjs read --target=arrangement_clip --track=2 --clip=0
```

Preserve the returned `notes` timing, phrase contour, and length unless the user explicitly asks for a rewrite.

For whole-set questions such as "which notes are off?", "what instruments belong?", or "what is too crowded?", audit the Set before answering:

```bash
scripts/live-bridge.mjs audit --tracks=8 --scenes=16 --notes=128
```

For A/B listening or sound changes, inspect first and keep snapshot ids:

```bash
scripts/live-bridge.mjs track-summary --track=2 --devices
scripts/live-bridge.mjs rename-track --track=5 --name="Alt Bass" --dry-run
scripts/live-bridge.mjs snapshot-mixer --tracks=2,5
scripts/live-bridge.mjs set-track --track=2 --solo=true --dry-run
scripts/live-bridge.mjs restore-mixer --snapshot=mixer-...
```

For common revisions, use `producer-move.mjs` first so the agent can move quickly without hand-building note lists:

```bash
scripts/producer-move.mjs dance-hook --key=A:min --write --replace --dry-run
scripts/producer-move.mjs dance-hook --key=A:min --write --replace
```

Intent mapping:

- "hazlo mas bailable" -> `dance-hook`
- "mas oscuro" / "darken it" -> `darken-hook`
- "mas luminoso" / "brighter" -> `brighten-hook`
- "simplifica" -> `simplify-hook`
- "dame bajo" / "bassline" -> `bassline`

Use `--dry-run` for payload inspection, `--out=/tmp/name.json` when a file artifact is useful, `--write --replace` only when the user has authorized changing the target clip, and `--fire` only when the user wants playback.

## Realtime Prompts To Say

Short spoken prompts work better:

```text
Make this darker but keep it danceable.
Send the current progression to Ableton.
Give me a quieter verse melody and keep it silent.
Play the Ableton clip.
Stop Live playback.
Make a hook variation with more lift.
Adapt this to my vocal range.
```

Avoid long multi-instruction prompts while Realtime is listening. Split into one creative move at a time.

## Feedback Forks

Use `request_user_input` for forks when available. The point is to keep the user choosing like a producer, not debugging options.

Good fork labels:

- “Keep it dark / add lift / make it more hypnotic”
- “Verse intimacy / hook energy / bridge contrast”
- “More space / more motion / more tension”
- “Send to Ableton / revise here / generate a second option”

Poor forks:

- “Do you like it?”
- “What do you want next?”
- “Should I continue?”

Checkpoint templates:

```text
Initial direction:
- "Dark danceable (Recommended)" — Minor color and steady pulse without making it gloomy.
- "Bright bittersweet" — More lift, clearer tonic, more singer-songwriter energy.
- "Sparse intimate" — Fewer chords, more vocal space, closer production.
```

```text
After first progression:
- "Send to Ableton (Recommended)" — Audition the loop through the current instrument.
- "Make darker" — Add borrowed color and lower the emotional center.
- "Generate alternate" — Keep the brief but try a different harmonic path.
```

```text
Arrangement choice:
- "Hook first (Recommended)" — Build the most memorable section before expanding.
- "Verse first" — Establish intimacy and leave room for later lift.
- "Bridge contrast" — Create a separate color to prevent loop fatigue.
```

```text
Vocal fit:
- "More singable (Recommended)" — Narrower range and clearer phrase landings.
- "More dramatic" — Wider contour and stronger arrival notes.
- "More rhythmic" — Shorter motifs that lock to the beat.
```

## When To Hand Off

Use `$chordchemist-composer` when:

- exact chord spellings, key distance, melody metrics, vocal range ranking, WAV/SVG render, or deterministic ChordChemist state matters.

Use `$ableton-songwriting-copilot` when:

- Realtime says permission denied;
- API key or SQLite readiness is unclear;
- bridge `/health` fails;
- M4L poller is missing;
- Ableton writes time out;
- Live is silent despite a written clip.
