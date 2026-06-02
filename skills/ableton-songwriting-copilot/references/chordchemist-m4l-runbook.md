# ChordChemist M4L Runbook

## Source Of Truth

Default repo:

```text
$CHORDCHEMIST_REPO
```

Current remote:

```text
https://github.com/ranvier2d2/chordchemist-m4l.git
```

Current app URL normally prints as:

```text
http://localhost:8080/
```

Producer status page:

```text
http://localhost:8080/m4l-integration
```

Default SQLite DB:

```text
~/.chordchemist-m4l/chordchemist.sqlite
```

Current local M4L device:

```text
~/Music/Ableton/User Library/Presets/MIDI Effects/Max MIDI Effect/ChordChemist Bridge.amxd
~/Music/Ableton/User Library/Presets/MIDI Effects/Max MIDI Effect/ChordChemist Bridge v12.amxd
```

Max search-path JS assets:

```text
~/Documents/Max 8/Library/chord-chemist-m4l-client-http.js
~/Documents/Max 8/Library/live-api-bridge.js
```

## Stack Startup

From the repo:

```bash
npm run dev
npm run live-bridge
```

Check app/local status:

```bash
curl -sS http://localhost:8080/api/local/status
```

Expected shape:

```json
{
  "openai": { "ok": true },
  "sqlite": { "ok": true },
  "scribe": { "ok": false }
}
```

`scribe.ok=false` only means the optional ElevenLabs Scribe mic button is unavailable. It does not block OpenAI Text Copilot or Realtime.

Check bridge:

```bash
curl -sS http://127.0.0.1:53873/health
```

Useful health fields:

- `queuedCommands`: should usually be `0`.
- `waitingPollers`: should be `1` when the M4L device is connected and waiting.

Agent-friendly stack check:

```bash
scripts/check-stack.sh --json
scripts/check-stack.sh --repo /path/to/chord-chemist --app-url http://localhost:8080 --bridge-url http://127.0.0.1:53873
```

The checker never prints API key values; it reports only present/missing.

## Realtime Voice

Requirements:

- `.env` has `OPENAI_API_KEY`.
- `/api/local/status` reports `openai.ok=true`.
- macOS Privacy & Security -> Microphone allows the app that owns the browser surface:
  - Codex for the in-app browser.
  - Google Chrome for Chrome.
- After changing macOS mic permission for Codex, close and reopen Codex.

Common symptom:

```text
Permission denied
```

Interpretation: browser `getUserMedia` was blocked. Check OS/browser mic permission before changing Realtime code or API keys.

## Ableton/M4L Flow

1. Start `npm run live-bridge`.
2. Open Ableton Live.
3. Put `ChordChemist Bridge v12.amxd` on a MIDI track.
4. Put an instrument after the bridge device, such as E-Piano.
5. Select/highlight the target clip slot.
6. Confirm `/health` has `waitingPollers: 1`.
7. Use Copilot or Realtime only after the user explicitly asks to send/write/play in Ableton.

M4L patch invariants:

```text
midiin -> midiout
loadbang -> script start -> node.script chord-chemist-m4l-client-http.js @autostart 1
node.script outlet 0 -> js live-api-bridge.js -> node.script inlet 0
loadbang/script start -> start_file_bridge -> js live-api-bridge.js file bridge fallback
loadbang/script start -> 1 -> metro 250 -> file_bridge_tick -> js live-api-bridge.js file bridge tick
```

The file bridge fallback writes JSON through Max's text-file API and uses
`/private/tmp/chordchemist-m4l-file-bridge` as the shared queue. If no
`/health.data.fileBridge.clients` entry appears after clicking `script start`, reload one fresh
`ChordChemist Bridge v12.amxd`; an already-loaded device may still have an older embedded patcher or
older JS instance.

Live 11 warning:

- Ableton may warn about an older MIDI note editing API.
- Continue for this prototype.
- The bridge writes pitch/start/duration/velocity and does not preserve MPE, probability, release velocity, or per-note metadata.

## Troubleshooting

### Copilot says API key missing

Check:

```bash
curl -sS http://localhost:8080/api/local/status
```

If `openai.ok=false`, create or fix repo `.env`:

```bash
OPENAI_API_KEY=<set-in-env>
OPENAI_AGENT_MODEL=gpt-5.5
OPENAI_REALTIME_MODEL=gpt-realtime-2
```

Restart the dev server if it was already running before `.env` changed.

### Realtime says Permission denied

Check macOS microphone permission. For Codex in-app browser, System Settings must show Codex microphone access as on, and Codex must be restarted after enabling it.

### Bridge health has waitingPollers 0

Load/reload the M4L device on a MIDI track. If Max editor windows were opened, close them and restart the bridge server to clear stale pollers.

### Commands time out

Likely causes:

- stale Node for Max poller from an open Max editor window;
- `node.script` child process cached older JS;
- bridge server has stale long-poll state.

Fast recovery:

```bash
pkill -f "tsx scripts/live-bridge-server.ts" || true
npm run live-bridge
```

Then reload the M4L device if needed.

### Clip writes but no sound

Check, in order:

1. MIDI track has an instrument after `ChordChemist Bridge`.
2. M4L device has `midiin -> midiout` pass-through.
3. Track monitor/routing allows playback.
4. Live meters move on the MIDI track and Master.

### Wrong clip changes

The bridge targets Ableton’s highlighted clip slot. Click the intended slot before sending a write/play command.

## Creative Workflow

For songwriting sessions:

1. Ground the current key, mode, progression, or desired vibe.
2. Generate a first sketch instead of over-questioning when the user gives enough intent.
3. Ask for feedback only when it changes musical identity: darker/brighter, more motion/more space, verse/hook/bridge, accept/revise/regenerate.
4. Keep Realtime and Copilot silent until the user asks to hear audio or send to Ableton.
5. When sending to Ableton, prefer separate audition clips or highlighted-slot writes that the user explicitly requested.

Use `$chordchemist-composer` for deterministic ChordChemist harmony, melody, vocal adaptation, SVG, or WAV work. Use this skill for local Ableton/Realtime/bridge operations around that musical work.

## Repo Checks

Before claiming implementation work is complete:

```bash
./node_modules/.bin/tsc --noEmit
npm run test:live-bridge
npm run test:realtime-copilot
npm run test:realtime-events
npm run build
```

For scoped lint:

```bash
./node_modules/.bin/eslint <touched files>
```

`npm run lint` is not currently a clean whole-repo gate because older files have unrelated Prettier debt.
