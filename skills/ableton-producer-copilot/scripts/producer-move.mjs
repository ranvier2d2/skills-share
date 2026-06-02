#!/usr/bin/env node
import fs from "node:fs";

const DEFAULT_BRIDGE_URL = "http://127.0.0.1:53873";
const bridgeUrl =
  process.env.CHORD_CHEMIST_LIVE_BRIDGE_URL ||
  process.env.CHORDCHEMIST_LIVE_BRIDGE_URL ||
  DEFAULT_BRIDGE_URL;

const EXIT = {
  GENERAL: 1,
  INVALID_ARGS: 2,
  BRIDGE_UNREACHABLE: 3,
  BRIDGE_REJECTED: 5,
};
const MOVES = new Set(["dance-hook", "darken-hook", "brighten-hook", "simplify-hook", "bassline"]);
const TARGETS = new Set(["highlighted_clip_slot", "session_clip_slot", "arrangement_clip", "detail_clip"]);
const FLAGS = new Set([
  "help",
  "dry-run",
  "compact",
  "pretty",
  "key",
  "bars",
  "name",
  "out",
  "write",
  "replace",
  "fire",
  "wait-ms",
  "target",
  "track",
  "scene",
  "clip",
  "client",
]);
const NOTE_TO_PC = {
  C: 0,
  "C#": 1,
  DB: 1,
  D: 2,
  "D#": 3,
  EB: 3,
  E: 4,
  F: 5,
  "F#": 6,
  GB: 6,
  G: 7,
  "G#": 8,
  AB: 8,
  A: 9,
  "A#": 10,
  BB: 10,
  B: 11,
};

class ScriptError extends Error {
  constructor(error, message, exitCode = EXIT.GENERAL, data = undefined) {
    super(message);
    this.error = error;
    this.exitCode = exitCode;
    this.data = data;
  }
}

/** Parses --flag=value, --flag value, and boolean --flag input without prompting. */
function parseCli(argv) {
  const flags = {};
  const positionals = [];
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (!arg.startsWith("--")) {
      positionals.push(arg);
      continue;
    }
    const raw = arg.slice(2);
    const eq = raw.indexOf("=");
    const name = eq >= 0 ? raw.slice(0, eq) : raw;
    if (!FLAGS.has(name)) {
      throw new ScriptError("invalid_flag", `Unknown flag --${name}`, EXIT.INVALID_ARGS, { allowedFlags: [...FLAGS].sort() });
    }
    if (eq >= 0) {
      flags[name] = raw.slice(eq + 1);
      continue;
    }
    const next = argv[index + 1];
    if (next && !next.startsWith("--")) {
      flags[name] = next;
      index += 1;
    } else {
      flags[name] = true;
    }
  }
  return { flags, positionals };
}

function flag(cli, name, fallback = undefined) {
  return Object.prototype.hasOwnProperty.call(cli.flags, name) ? cli.flags[name] : fallback;
}

function hasFlag(cli, name) {
  return Object.prototype.hasOwnProperty.call(cli.flags, name);
}

function stringFlag(cli, name, fallback = "") {
  const value = flag(cli, name, fallback);
  return value == null || value === true ? fallback : String(value);
}

function numberFlag(cli, name, fallback = undefined, options = {}) {
  const value = flag(cli, name, fallback);
  if (value == null || value === "") return undefined;
  const number = Number(value);
  if (!Number.isFinite(number)) {
    throw new ScriptError("invalid_number", `--${name} must be a finite number. Received: ${JSON.stringify(value)}`, EXIT.INVALID_ARGS);
  }
  if (options.integer && !Number.isInteger(number)) {
    throw new ScriptError("invalid_integer", `--${name} must be an integer. Received: ${JSON.stringify(value)}`, EXIT.INVALID_ARGS);
  }
  if (options.min != null && number < options.min) {
    throw new ScriptError("number_too_small", `--${name} must be >= ${options.min}. Received: ${number}`, EXIT.INVALID_ARGS);
  }
  if (options.max != null && number > options.max) {
    throw new ScriptError("number_too_large", `--${name} must be <= ${options.max}. Received: ${number}`, EXIT.INVALID_ARGS);
  }
  return number;
}

function outputJson(value, cli) {
  const spaces = hasFlag(cli, "compact") && !hasFlag(cli, "pretty") ? 0 : 2;
  process.stdout.write(`${JSON.stringify(value, null, spaces)}\n`);
}

function errorJson(error) {
  process.stderr.write(
    `${JSON.stringify(
      {
        ok: false,
        error: error.error || "script_error",
        message: error.message,
        ...(error.data ? { data: error.data } : {}),
      },
      null,
      2,
    )}\n`,
  );
}

function commandId(type) {
  return `skill-${type}-${Date.now()}`;
}

function parseKey(input) {
  const [rawTonic = "A", rawMode = "min"] = String(input || "A:min").split(":");
  const tonic = rawTonic.trim().toUpperCase();
  const mode = rawMode.trim().toLowerCase().startsWith("maj") ? "maj" : "min";
  const pc = NOTE_TO_PC[tonic];
  if (pc === undefined) {
    throw new ScriptError("unsupported_key", `Unsupported key tonic: ${rawTonic}`, EXIT.INVALID_ARGS, {
      supportedTonics: Object.keys(NOTE_TO_PC),
    });
  }
  return { tonic, mode, pc };
}

function midiFromPc(pc, octave) {
  return 12 * (octave + 1) + ((pc % 12) + 12) % 12;
}

function nearestInRange(pc, min, max) {
  for (let pitch = min; pitch <= max; pitch += 1) {
    if (pitch % 12 === ((pc % 12) + 12) % 12) return pitch;
  }
  return min;
}

function chordPcs(rootPc, quality) {
  if (quality === "min7") return [rootPc, rootPc + 3, rootPc + 7, rootPc + 10];
  if (quality === "maj7") return [rootPc, rootPc + 4, rootPc + 7, rootPc + 11];
  if (quality === "dom7") return [rootPc, rootPc + 4, rootPc + 7, rootPc + 10];
  if (quality === "min") return [rootPc, rootPc + 3, rootPc + 7];
  return [rootPc, rootPc + 4, rootPc + 7];
}

function voicedChord(rootPc, quality, low = 52, high = 74) {
  return chordPcs(rootPc, quality)
    .map((pc) => nearestInRange(pc, low, high))
    .sort((a, b) => a - b);
}

function pushChord(notes, pitches, startTime, duration, velocity) {
  pitches.forEach((pitch, index) => {
    notes.push({
      pitch,
      startTime,
      duration,
      velocity: Math.max(1, Math.min(127, velocity - index * 2)),
    });
  });
}

function pushBass(notes, pitch, startTime, duration, velocity) {
  notes.push({ pitch, startTime, duration, velocity });
}

/** Returns a simple four-chord palette for fast producer moves, not a full composition engine. */
function progressionFor(key, selectedMove) {
  if (key.mode === "maj") {
    return [
      { degree: 0, quality: "maj", bass: 0 },
      { degree: 7, quality: "maj", bass: 7 },
      { degree: 9, quality: "min", bass: 9 },
      { degree: 5, quality: "maj", bass: 5 },
    ];
  }
  if (selectedMove === "darken-hook") {
    return [
      { degree: 0, quality: "min7", bass: 0 },
      { degree: 8, quality: "maj7", bass: 8 },
      { degree: 5, quality: "min7", bass: 5 },
      { degree: 10, quality: "dom7", bass: 10 },
    ];
  }
  if (selectedMove === "brighten-hook") {
    return [
      { degree: 0, quality: "min", bass: 0 },
      { degree: 3, quality: "maj", bass: 3 },
      { degree: 8, quality: "maj", bass: 8 },
      { degree: 10, quality: "maj", bass: 10 },
    ];
  }
  return [
    { degree: 0, quality: "min", bass: 0 },
    { degree: 8, quality: "maj", bass: 8 },
    { degree: 3, quality: "maj", bass: 3 },
    { degree: 10, quality: "maj", bass: 10 },
  ];
}

/** Builds a LiveBridge MIDI clip from a named producer move. */
function generateHook(selectedMove, options) {
  const key = parseKey(options.key);
  const bars = Math.max(1, Math.min(16, Number(options.bars) || 4));
  const progression = progressionFor(key, selectedMove);
  const notes = [];
  const name = options.name || defaultName(selectedMove, key);

  for (let bar = 0; bar < bars; bar += 1) {
    const chord = progression[bar % progression.length];
    const start = bar * 4;
    const rootPc = key.pc + chord.degree;
    const bassPc = key.pc + chord.bass;
    const bassPitch = nearestInRange(bassPc, 36, 50);
    const chordNotes = voicedChord(rootPc, chord.quality, selectedMove === "darken-hook" ? 48 : 52, 76);

    if (selectedMove === "simplify-hook") {
      pushBass(notes, bassPitch, start, 0.5, 92);
      pushChord(notes, chordNotes, start, 3.75, 86);
      continue;
    }

    if (selectedMove === "bassline") {
      const fifth = nearestInRange(bassPc + 7, 36, 55);
      const octave = bassPitch + 12 <= 60 ? bassPitch + 12 : bassPitch;
      pushBass(notes, bassPitch, start, 0.45, 102);
      pushBass(notes, octave, start + 0.75, 0.22, 84);
      pushBass(notes, fifth, start + 1.5, 0.28, 88);
      pushBass(notes, bassPitch, start + 2, 0.42, 96);
      pushBass(notes, octave, start + 2.75, 0.2, 86);
      pushBass(notes, fifth, start + 3.5, 0.25, 92);
      continue;
    }

    const chordVelocity = selectedMove === "darken-hook" ? 84 : 92;
    pushBass(notes, bassPitch, start, 0.45, 96);
    pushChord(notes, chordNotes, start + 0.5, 0.32, chordVelocity);
    pushChord(notes, chordNotes.slice(1), start + 1.5, 0.25, chordVelocity - 4);
    pushBass(notes, bassPitch, start + 2, 0.4, 90);
    pushChord(notes, chordNotes.slice(-3), start + 2.75, 0.18, chordVelocity + 2);

    const top = topLinePitches(key, selectedMove, bar);
    top.forEach((pitch, index) => {
      notes.push({
        pitch,
        startTime: start + 3.25 + index * 0.25,
        duration: index === top.length - 1 ? 0.23 : 0.18,
        velocity: 92 + index * 4,
      });
    });
  }

  return {
    name,
    lengthBeats: bars * 4,
    notes: notes.sort((a, b) => a.startTime - b.startTime || a.pitch - b.pitch),
  };
}

function topLinePitches(key, selectedMove, bar) {
  const minorScale = [0, 2, 3, 5, 7, 8, 10, 12];
  const majorScale = [0, 2, 4, 5, 7, 9, 11, 12];
  const scale = key.mode === "maj" ? majorScale : minorScale;
  const shapes = {
    "dance-hook": [
      [4, 5, 6],
      [5, 6, 7],
      [7, 6, 5],
      [5, 4, 3],
    ],
    "darken-hook": [
      [3, 2, 1],
      [4, 3, 2],
      [2, 1, 0],
      [3, 2, 1],
    ],
    "brighten-hook": [
      [5, 6, 7],
      [6, 7, 8],
      [7, 8, 7],
      [6, 7, 8],
    ],
  };
  const degrees = (shapes[selectedMove] || shapes["dance-hook"])[bar % 4];
  return degrees.map((degree) => midiFromPc(key.pc + scale[degree], 4));
}

function defaultName(selectedMove, key) {
  const names = {
    "dance-hook": "Hook bailable",
    "darken-hook": "Hook darker",
    "brighten-hook": "Hook brighter",
    "simplify-hook": "Hook simplified",
    bassline: "Dance bassline",
  };
  return `${names[selectedMove] || "Producer move"} ${key.tonic}:${key.mode}`;
}

function readTargetFlags(cli) {
  const target = stringFlag(cli, "target", "highlighted_clip_slot");
  if (!TARGETS.has(target)) {
    throw new ScriptError("invalid_target", "--target must be one of highlighted_clip_slot, session_clip_slot, arrangement_clip, detail_clip", EXIT.INVALID_ARGS, {
      received: target,
    });
  }
  const trackIndex = numberFlag(cli, "track", undefined, { integer: true, min: 0 });
  const sceneIndex = numberFlag(cli, "scene", undefined, { integer: true, min: 0 });
  const arrangementClipIndex = numberFlag(cli, "clip", undefined, { integer: true, min: 0 });
  if (target === "session_clip_slot" && (trackIndex == null || sceneIndex == null)) {
    throw new ScriptError("missing_target_coordinate", "--target=session_clip_slot requires --track and --scene", EXIT.INVALID_ARGS);
  }
  if (target === "arrangement_clip" && (trackIndex == null || arrangementClipIndex == null)) {
    throw new ScriptError("missing_target_coordinate", "--target=arrangement_clip requires --track and --clip", EXIT.INVALID_ARGS);
  }
  return {
    target,
    ...(trackIndex != null ? { trackIndex } : {}),
    ...(sceneIndex != null ? { sceneIndex } : {}),
    ...(arrangementClipIndex != null ? { arrangementClipIndex } : {}),
  };
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(new URL(path, bridgeUrl), {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
  } catch (error) {
    throw new ScriptError("bridge_unreachable", `Could not reach bridge at ${bridgeUrl}: ${error.message}`, EXIT.BRIDGE_UNREACHABLE);
  }
  const text = await response.text();
  if (!response.ok) throw new ScriptError("bridge_http_error", `Bridge returned HTTP ${response.status}`, EXIT.BRIDGE_UNREACHABLE, { body: text });
  return text.trim() ? JSON.parse(text) : {};
}

async function dispatch(payload, waitMs) {
  const result = await request(`/commands?waitMs=${waitMs}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (result && result.ok === false) {
    throw new ScriptError("bridge_rejected_command", result.message || result.error || "Bridge rejected command", EXIT.BRIDGE_REJECTED, result);
  }
  return result;
}

function withClient(cli, payload) {
  const clientId = stringFlag(cli, "client", "");
  return clientId ? { ...payload, clientId } : payload;
}

function buildWritePayload(move, clip, cli) {
  return withClient(cli, {
    id: commandId(move),
    type: "write_midi_clip",
    ...readTargetFlags(cli),
    replaceExisting: hasFlag(cli, "replace"),
    clip,
  });
}

function buildFirePayload(cli) {
  return withClient(cli, {
    id: commandId("fire"),
    type: "fire_clip",
    ...readTargetFlags(cli),
  });
}

function help() {
  return {
    ok: true,
    script: "scripts/producer-move.mjs",
    description: "Generate common Ableton-ready MIDI producer moves and optionally send them to the Live bridge.",
    prerequisites: ["Node.js 18+", "Bridge server and loaded M4L device only when using --write or --fire"],
    usage: "scripts/producer-move.mjs <dance-hook|darken-hook|brighten-hook|simplify-hook|bassline> [options]",
    moves: [...MOVES],
    options: {
      "--key": "Tonic and mode, for example A:min, D:min, C:maj. Default: A:min.",
      "--bars": "Clip length in bars, 1-16. Default: 4.",
      "--name": "Clip name override.",
      "--out": "Write clip JSON to this path in addition to stdout.",
      "--write": "Send the generated clip to Ableton.",
      "--replace": "Replace existing target clip when writing.",
      "--fire": "Fire the target after a successful write.",
      "--target": "highlighted_clip_slot, session_clip_slot, arrangement_clip, detail_clip.",
      "--track/--scene/--clip": "Target coordinates when using explicit targets.",
      "--dry-run": "Print clip and bridge payloads without writing to files or Ableton.",
      "--compact": "Print compact JSON.",
    },
    examples: [
      "scripts/producer-move.mjs dance-hook --key=A:min --out=/tmp/hook.json",
      "scripts/producer-move.mjs dance-hook --key=A:min --write --target=session_clip_slot --track=0 --scene=2 --replace --dry-run",
      "scripts/producer-move.mjs darken-hook --key=D:min --write --replace --fire",
      "scripts/producer-move.mjs bassline --key=A:min",
    ],
    exitCodes: {
      0: "success",
      [EXIT.GENERAL]: "general runtime error",
      [EXIT.INVALID_ARGS]: "invalid arguments",
      [EXIT.BRIDGE_UNREACHABLE]: "bridge HTTP server unreachable or returned HTTP error",
      [EXIT.BRIDGE_REJECTED]: "bridge returned ok=false for a command",
    },
  };
}

async function main() {
  const cli = parseCli(process.argv.slice(2));
  const move = cli.positionals[0] || "help";
  if (move === "help" || move === "--help" || move === "-h" || hasFlag(cli, "help")) {
    outputJson(help(), cli);
    return;
  }
  if (!MOVES.has(move)) {
    throw new ScriptError("unknown_move", `Unknown producer move: ${move}`, EXIT.INVALID_ARGS, { moves: [...MOVES] });
  }

  const clip = generateHook(move, {
    key: stringFlag(cli, "key", "A:min"),
    bars: numberFlag(cli, "bars", 4, { integer: true, min: 1, max: 16 }),
    name: stringFlag(cli, "name", ""),
  });
  const waitMs = numberFlag(cli, "wait-ms", 15000, { integer: true, min: 1 });
  const out = stringFlag(cli, "out", "");
  const writePayload = hasFlag(cli, "write") ? buildWritePayload(move, clip, cli) : undefined;
  const firePayload = hasFlag(cli, "fire") ? buildFirePayload(cli) : undefined;

  if (hasFlag(cli, "dry-run")) {
    outputJson(
      {
        ok: true,
        dryRun: true,
        bridgeUrl,
        waitMs,
        clip,
        outputFile: out || undefined,
        writeCommand: writePayload,
        fireCommand: firePayload,
      },
      cli,
    );
    return;
  }

  if (out) fs.writeFileSync(out, `${JSON.stringify(clip, null, 2)}\n`);

  if (writePayload) {
    const writeResult = await dispatch(writePayload, waitMs);
    const result = { ok: true, clip, outputFile: out || undefined, writeResult };
    if (firePayload && writeResult.ok) {
      result.fireResult = await dispatch(firePayload, Math.min(waitMs, 8000));
    }
    outputJson(result, cli);
    return;
  }

  outputJson({ ok: true, clip, outputFile: out || undefined }, cli);
}

main().catch((error) => {
  const normalized =
    error instanceof ScriptError
      ? error
      : new ScriptError("script_error", error instanceof Error ? error.message : String(error), EXIT.GENERAL);
  errorJson(normalized);
  process.exit(normalized.exitCode);
});
