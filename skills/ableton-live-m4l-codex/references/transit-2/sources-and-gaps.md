# Transit 2 Sources And Gaps

Independent research summary for the `references/transit-2` pack.

## Gaps To Cover

- Exact Ableton automation behavior for third-party plugin parameters:
  AbletonOSC can read/write exposed macro values, but Arrangement automation
  writing still needs a robust bridge/UI workflow.
- Preset state inventory:
  we know the current preset is `A Meta Filter`, but the skill does not yet
  know how to enumerate or select Transit 2 presets reliably from scripts.
- Safe point map:
  we have baseline `0.1320969164` and safe expressive point `0.2`; we still
  need at least one edge/risk point before generating real curves by rule.
- Sidechain routing:
  Transit 2 supports sidechain mode, but the current bridge references need a
  repeatable Ableton-side procedure for choosing the sidechain source.
- Latency/performance:
  Pitch+, Warp, Loop, Reverser, OTT, heavy feedback, and preset switching need
  explicit listening and CPU/latency checks before performance use.
- Tails and loopability:
  delay/reverb tails should be documented per preset because tails can either
  smooth transitions or smear the next downbeat.

## Sources

1. Baby Audio product page
   URL: https://babyaud.io/transit
   Why it matters: official positioning, motion modes, effect count, preset
   count, DAW support, and creative use cases.

2. Baby Audio Transit 2 manual
   URL: https://www.lootaudio.com/_media/images/loot/Baby%20Audio/transit-2/Transit%2B2%2BBaby%2BAudio%2BManual.pdf
   Why it matters: operational details for macro linking, motion modes,
   sidechain, gate/sequencer behavior, tails, smoothing, MIDI learn, preset
   panel, and module descriptions.

3. Baby Audio Andrew Huang interview
   URL: https://babyaud.io/blog/andrew-huang-interview
   Why it matters: explains the design intent behind Transit 2, especially the
   idea of using the macro as a sweet spot finder and going beyond buildups.

4. Baby Audio transitions article
   URL: https://babyaud.io/blog/drops-risers-sfx
   Why it matters: practical transition recipes: risers, delay/reverb washes,
   filtered noise, and the macro control workflow.

5. MusicTech Transit 2 review
   URL: https://musictech.com/reviews/plug-ins/baby-audio-transit-2-review-andrew-huang/
   Why it matters: external review, 9/10 rating, notes that Transit 2 simplifies
   complex automation but overuse is a real danger.

6. MusicTech Transit 2 launch/news
   URL: https://musictech.com/news/gear/baby-audio-transit-2/
   Why it matters: concise summary of v2 additions: four added motion modes,
   ten new effects, and curated preset context.

7. CDM Transit 2 hands-on
   URL: https://cdm.link/transit-2/
   Why it matters: independent music-tech framing: Transit 2 as a motion
   multi-effects workstation, not only a transition designer.

8. Baby Audio forum: Pitch+ latency note
   URL: https://forum.babyaud.io/t/transit-2-pitch-has-no-module-on-off-button/344
   Why it matters: support discussion documenting Pitch+ latency and live-use
   caution from Baby Audio support.

## Recommendations For This Reference Pack

- Keep this README focused on agent action, not product marketing.
- Keep exact session values in a structured safe-points manifest in the repo;
  this folder should explain how to use those values musically.
- Add a preset audit artifact after each listening session:
  `preset`, `macro_baseline`, `safe_points`, `risk_point`, `section_intention`.
- Add sidechain routing notes only after verifying in Ableton UI and/or bridge.
- Prefer Arrangement automation plans over direct writes until the bridge can
  prove lane creation with readback and producer listening approval.
