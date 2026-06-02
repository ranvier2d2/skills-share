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

const TARGETS = new Set(["highlighted_clip_slot", "session_clip_slot", "arrangement_clip", "detail_clip"]);
const READ_ONLY_COMMANDS = new Set([
  "health",
  "state",
  "context",
  "audit",
  "session-summary",
  "arrangement-summary",
  "track-summary",
  "device-summary",
  "read",
  "watch-clip-requests",
]);
const STATEFUL_NON_LIVE_MUTATIONS = new Set(["snapshot-mixer"]);
const LIVE_MUTATIONS = new Set([
  "rename-track",
  "rename-scene",
  "set-track",
  "restore-mixer",
  "set-device-param",
  "restore-device-param",
  "set-clip-status",
  "set-arrangement-end",
  "write",
  "smoke-write",
  "duplicate-to-arrangement",
  "fire",
  "stop",
]);
const COMMAND_DETAILS = {
  health: { mutability: "read-only", flags: [], example: "scripts/live-bridge.mjs health" },
  state: { mutability: "read-only", flags: ["--target", "--track", "--scene", "--clip"], example: "scripts/live-bridge.mjs state --target=session_clip_slot --track=0 --scene=2" },
  context: { mutability: "read-only", flags: ["--tracks", "--scenes"], example: "scripts/live-bridge.mjs context --tracks=8 --scenes=16" },
  audit: { mutability: "read-only", flags: ["--tracks", "--scenes", "--arrangement-clips", "--notes", "--no-devices", "--devices", "--params"], example: "scripts/live-bridge.mjs audit --tracks=8 --scenes=16 --notes=128" },
  "session-summary": { mutability: "read-only", flags: ["--tracks", "--scenes"], example: "scripts/live-bridge.mjs session-summary --tracks=8 --scenes=16" },
  "arrangement-summary": { mutability: "read-only", flags: ["--tracks"], example: "scripts/live-bridge.mjs arrangement-summary --tracks=8" },
  "track-summary": { mutability: "read-only", flags: ["--track", "--tracks", "--devices", "--devices-max", "--params"], example: "scripts/live-bridge.mjs track-summary --track=2 --devices" },
  "device-summary": { mutability: "read-only", flags: ["--track", "--devices", "--params"], example: "scripts/live-bridge.mjs device-summary --track=2 --params=24" },
  read: { mutability: "read-only", flags: ["--target", "--track", "--scene", "--clip", "--start", "--span", "--from-pitch", "--pitch-span"], example: "scripts/live-bridge.mjs read --target=arrangement_clip --track=2 --clip=0" },
  write: { mutability: "mutates-live", flags: ["CLIP_JSON_OR_-", "--target", "--track", "--scene", "--clip", "--replace"], example: "scripts/live-bridge.mjs write ./clip.json --target=session_clip_slot --track=0 --scene=2 --replace --dry-run" },
  "smoke-write": { mutability: "mutates-live", flags: ["--target", "--track", "--scene", "--clip", "--replace"], example: "scripts/live-bridge.mjs smoke-write --replace --dry-run" },
  "rename-track": { mutability: "mutates-live", flags: ["--track", "--name"], example: "scripts/live-bridge.mjs rename-track --track=5 --name='Alt Bass' --dry-run" },
  "rename-scene": { mutability: "mutates-live", flags: ["--scene", "--name"], example: "scripts/live-bridge.mjs rename-scene --scene=0 --name='Verse' --dry-run" },
  "set-track": { mutability: "mutates-live", flags: ["--track", "--mute", "--solo", "--arm", "--volume", "--pan", "--label"], example: "scripts/live-bridge.mjs set-track --track=2 --solo=true --dry-run" },
  "snapshot-mixer": { mutability: "stateful-non-live", flags: ["--tracks", "--label"], example: "scripts/live-bridge.mjs snapshot-mixer --tracks=2,5" },
  "restore-mixer": { mutability: "mutates-live", flags: ["--snapshot"], example: "scripts/live-bridge.mjs restore-mixer --snapshot=mixer-123" },
  "set-device-param": { mutability: "mutates-live", flags: ["--track", "--device", "--param", "--value", "--label"], example: "scripts/live-bridge.mjs set-device-param --track=2 --device=0 --param=5 --value=0.42 --dry-run" },
  "restore-device-param": { mutability: "mutates-live", flags: ["--snapshot"], example: "scripts/live-bridge.mjs restore-device-param --snapshot=device-123" },
  "set-clip-status": { mutability: "mutates-live", flags: ["--target", "--track", "--scene", "--clip", "--name", "--color"], example: "scripts/live-bridge.mjs set-clip-status --target=session_clip_slot --track=0 --scene=0 --name='CC: ready' --color=65280 --dry-run" },
  "watch-clip-requests": { mutability: "read-only", flags: ["--prefix", "--tracks", "--scenes"], example: "scripts/live-bridge.mjs watch-clip-requests --prefix=cc:" },
  "set-arrangement-end": { mutability: "mutates-live", flags: ["--track", "--clip", "--end"], example: "scripts/live-bridge.mjs set-arrangement-end --track=0 --clip=1 --end=48 --dry-run" },
  "duplicate-to-arrangement": { mutability: "mutates-live", flags: ["--track", "--scene", "--start"], example: "scripts/live-bridge.mjs duplicate-to-arrangement --track=0 --scene=1 --start=16 --dry-run" },
  fire: { mutability: "mutates-live", flags: ["--target", "--track", "--scene"], example: "scripts/live-bridge.mjs fire --dry-run" },
  stop: { mutability: "mutates-live", flags: ["--target", "--track", "--scene"], example: "scripts/live-bridge.mjs stop --dry-run" },
};
const COMMANDS = new Set([...READ_ONLY_COMMANDS, ...STATEFUL_NON_LIVE_MUTATIONS, ...LIVE_MUTATIONS]);
const GLOBAL_FLAGS = new Set([
  "help",
  "dry-run",
  "compact",
  "pretty",
  "wait-ms",
  "client",
  "target",
  "track",
  "scene",
  "clip",
  "start",
  "span",
  "from-pitch",
  "pitch-span",
  "tracks",
  "scenes",
  "arrangement-clips",
  "notes",
  "no-devices",
  "devices",
  "devices-max",
  "params",
  "mute",
  "solo",
  "arm",
  "volume",
  "pan",
  "label",
  "name",
  "snapshot",
  "device",
  "param",
  "value",
  "color",
  "prefix",
  "end",
  "replace",
]);

class ScriptError extends Error {
  constructor(error, message, exitCode = EXIT.GENERAL, data = undefined) {
    super(message);
    this.error = error;
    this.exitCode = exitCode;
    this.data = data;
  }
}

/**
 * Parses agent-friendly flags. Supports --flag=value, --flag value, and boolean --flag.
 */
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
    if (!GLOBAL_FLAGS.has(name)) {
      throw new ScriptError("invalid_flag", `Unknown flag --${name}`, EXIT.INVALID_ARGS, {
        allowedFlags: [...GLOBAL_FLAGS].sort(),
      });
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
  return number;
}

function booleanFlag(cli, name) {
  const value = flag(cli, name, undefined);
  if (value == null) return undefined;
  if (value === true || value === "true" || value === "1") return true;
  if (value === "false" || value === "0") return false;
  throw new ScriptError("invalid_boolean", `--${name} must be true/false or 1/0. Received: ${JSON.stringify(value)}`, EXIT.INVALID_ARGS);
}

function stringFlag(cli, name, fallback = "") {
  const value = flag(cli, name, fallback);
  return value == null || value === true ? fallback : String(value);
}

function outputJson(value, cli) {
  const spaces = hasFlag(cli, "compact") && !hasFlag(cli, "pretty") ? 0 : 2;
  process.stdout.write(`${JSON.stringify(value, null, spaces)}\n`);
}

function errorJson(error) {
  const payload = {
    ok: false,
    error: error.error || "script_error",
    message: error.message,
    ...(error.data ? { data: error.data } : {}),
  };
  process.stderr.write(`${JSON.stringify(payload, null, 2)}\n`);
}

function commandId(type) {
  return `skill-${type}-${Date.now()}`;
}

function withClient(cli, payload) {
  const clientId = stringFlag(cli, "client", "");
  return clientId ? { ...payload, clientId } : payload;
}

/**
 * Builds and validates the bridge target object shared by read/write/fire/status commands.
 */
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

function parseTrackList(cli) {
  const raw = stringFlag(cli, "tracks", "");
  if (!raw) return undefined;
  const indexes = raw
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const number = Number(item);
      if (!Number.isInteger(number) || number < 0) {
        throw new ScriptError("invalid_track_list", "--tracks must be a comma-separated list of non-negative integers", EXIT.INVALID_ARGS, {
          received: raw,
        });
      }
      return number;
    });
  return indexes.length > 0 ? indexes : undefined;
}

function readClipArg(cli) {
  const source = cli.positionals[1];
  if (!source) {
    throw new ScriptError("missing_clip", "write requires a clip JSON file path or '-' for stdin", EXIT.INVALID_ARGS);
  }
  let text;
  try {
    text = source === "-" ? fs.readFileSync(0, "utf8") : fs.readFileSync(source, "utf8");
  } catch (error) {
    throw new ScriptError("clip_read_failed", `Could not read clip JSON from ${source}: ${error.message}`, EXIT.INVALID_ARGS);
  }
  try {
    const parsed = JSON.parse(text);
    return parsed.clip || parsed;
  } catch (error) {
    throw new ScriptError("invalid_clip_json", `Could not parse clip JSON from ${source}: ${error.message}`, EXIT.INVALID_ARGS);
  }
}

function smokeClip() {
  const chords = [
    [60, 64, 67],
    [67, 71, 74],
    [69, 72, 76],
    [65, 69, 72],
  ];
  return {
    name: "ChordChemist Skill Smoke",
    lengthBeats: 16,
    notes: chords.flatMap((pitches, index) =>
      pitches.map((pitch) => ({
        pitch,
        startTime: index * 4,
        duration: 3.95,
        velocity: 90,
      })),
    ),
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
  if (!response.ok) {
    throw new ScriptError("bridge_http_error", `Bridge returned HTTP ${response.status}`, EXIT.BRIDGE_UNREACHABLE, { body: text });
  }
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

function buildCommandPayload(command, cli) {
  const targetArgs = readTargetFlags(cli);
  switch (command) {
    case "state":
      return withClient(cli, { id: commandId("state"), type: "get_live_state", ...targetArgs });
    case "context":
      return withClient(cli, {
        id: commandId("context"),
        type: "get_cached_live_context",
        maxTracks: numberFlag(cli, "tracks", 16, { integer: true, min: 1 }),
        maxScenes: numberFlag(cli, "scenes", 16, { integer: true, min: 1 }),
      });
    case "audit":
      return withClient(cli, {
        id: commandId("audit"),
        type: "audit_set",
        maxTracks: numberFlag(cli, "tracks", 16, { integer: true, min: 1 }),
        maxScenes: numberFlag(cli, "scenes", 16, { integer: true, min: 1 }),
        maxArrangementClips: numberFlag(cli, "arrangement-clips", 32, { integer: true, min: 0 }),
        maxNotesPerClip: numberFlag(cli, "notes", 256, { integer: true, min: 1 }),
        includeDevices: !hasFlag(cli, "no-devices"),
        maxDevices: numberFlag(cli, "devices", 8, { integer: true, min: 0 }),
        maxParameters: numberFlag(cli, "params", 16, { integer: true, min: 0 }),
      });
    case "read":
      return withClient(cli, {
        id: commandId("read"),
        type: "read_midi_clip",
        ...targetArgs,
        startBeat: numberFlag(cli, "start", undefined, { min: 0 }),
        beatSpan: numberFlag(cli, "span", undefined, { min: 0 }),
        fromPitch: numberFlag(cli, "from-pitch", undefined, { integer: true, min: 0 }),
        pitchSpan: numberFlag(cli, "pitch-span", undefined, { integer: true, min: 1 }),
      });
    case "track-summary":
      return withClient(cli, {
        id: commandId("track-summary"),
        type: "get_track_summary",
        trackIndex: numberFlag(cli, "track", undefined, { integer: true, min: 0 }),
        maxTracks: numberFlag(cli, "tracks", 16, { integer: true, min: 1 }),
        includeDevices: hasFlag(cli, "devices"),
        maxDevices: numberFlag(cli, "devices-max", 8, { integer: true, min: 0 }),
        maxParameters: numberFlag(cli, "params", 16, { integer: true, min: 0 }),
      });
    case "device-summary":
      return withClient(cli, {
        id: commandId("device-summary"),
        type: "get_device_summary",
        trackIndex: numberFlag(cli, "track", 0, { integer: true, min: 0 }),
        maxDevices: numberFlag(cli, "devices", 8, { integer: true, min: 0 }),
        maxParameters: numberFlag(cli, "params", 32, { integer: true, min: 0 }),
      });
    case "set-track": {
      const controls = {};
      for (const key of ["mute", "solo", "arm"]) {
        const value = booleanFlag(cli, key);
        if (value != null) controls[key] = value;
      }
      for (const key of ["volume", "pan"]) {
        const value = numberFlag(cli, key, undefined);
        if (value != null) controls[key] = value;
      }
      if (Object.keys(controls).length === 0) {
        throw new ScriptError("missing_track_control", "set-track requires at least one of --mute, --solo, --arm, --volume, or --pan", EXIT.INVALID_ARGS);
      }
      return withClient(cli, {
        id: commandId("set-track"),
        type: "set_track_controls",
        trackIndex: requiredNumber(cli, "track", "set-track requires --track", { integer: true, min: 0 }),
        controls,
        snapshotLabel: stringFlag(cli, "label", "skill set-track"),
      });
    }
    case "rename-track":
      return withClient(cli, {
        id: commandId("rename-track"),
        type: "set_track_name",
        trackIndex: requiredNumber(cli, "track", "rename-track requires --track", { integer: true, min: 0 }),
        name: requiredString(cli, "name", "rename-track requires --name"),
      });
    case "rename-scene":
      return withClient(cli, {
        id: commandId("rename-scene"),
        type: "set_scene_name",
        sceneIndex: requiredNumber(cli, "scene", "rename-scene requires --scene", { integer: true, min: 0 }),
        name: requiredString(cli, "name", "rename-scene requires --name"),
      });
    case "snapshot-mixer":
      return withClient(cli, {
        id: commandId("snapshot-mixer"),
        type: "snapshot_mixer_state",
        trackIndexes: parseTrackList(cli),
        snapshotLabel: stringFlag(cli, "label", "skill snapshot-mixer"),
      });
    case "restore-mixer":
      return withClient(cli, {
        id: commandId("restore-mixer"),
        type: "restore_mixer_snapshot",
        snapshotId: requiredString(cli, "snapshot", "restore-mixer requires --snapshot"),
      });
    case "set-device-param":
      return withClient(cli, {
        id: commandId("set-device-param"),
        type: "set_device_parameter",
        trackIndex: requiredNumber(cli, "track", "set-device-param requires --track", { integer: true, min: 0 }),
        deviceIndex: requiredNumber(cli, "device", "set-device-param requires --device", { integer: true, min: 0 }),
        parameterIndex: requiredNumber(cli, "param", "set-device-param requires --param", { integer: true, min: 0 }),
        value: requiredNumber(cli, "value", "set-device-param requires --value"),
        snapshotLabel: stringFlag(cli, "label", "skill set-device-param"),
      });
    case "restore-device-param":
      return withClient(cli, {
        id: commandId("restore-device-param"),
        type: "restore_device_parameter_snapshot",
        snapshotId: requiredString(cli, "snapshot", "restore-device-param requires --snapshot"),
      });
    case "watch-clip-requests":
      return withClient(cli, {
        id: commandId("watch-clip-requests"),
        type: "watch_named_clip_requests",
        prefix: stringFlag(cli, "prefix", "cc:"),
        maxTracks: numberFlag(cli, "tracks", 16, { integer: true, min: 1 }),
        maxScenes: numberFlag(cli, "scenes", 16, { integer: true, min: 1 }),
      });
    case "session-summary":
      return withClient(cli, {
        id: commandId("session-summary"),
        type: "get_session_clip_summary",
        maxTracks: numberFlag(cli, "tracks", 16, { integer: true, min: 1 }),
        maxScenes: numberFlag(cli, "scenes", 16, { integer: true, min: 1 }),
      });
    case "arrangement-summary":
      return withClient(cli, {
        id: commandId("arrangement-summary"),
        type: "get_arrangement_clip_summary",
        maxTracks: numberFlag(cli, "tracks", 16, { integer: true, min: 1 }),
      });
    case "set-arrangement-end":
      return withClient(cli, {
        id: commandId("set-arrangement-end"),
        type: "set_arrangement_clip_end_time",
        trackIndex: requiredNumber(cli, "track", "set-arrangement-end requires --track", { integer: true, min: 0 }),
        arrangementClipIndex: requiredNumber(cli, "clip", "set-arrangement-end requires --clip", { integer: true, min: 0 }),
        endBeat: requiredNumber(cli, "end", "set-arrangement-end requires --end", { min: 0 }),
      });
    case "fire":
    case "stop":
      return withClient(cli, {
        id: commandId(command),
        type: command === "fire" ? "fire_clip" : "stop_clip",
        ...targetArgs,
      });
    case "duplicate-to-arrangement":
      return withClient(cli, {
        id: commandId("duplicate-to-arrangement"),
        type: "duplicate_clip_to_arrangement",
        trackIndex: requiredNumber(cli, "track", "duplicate-to-arrangement requires --track", { integer: true, min: 0 }),
        sceneIndex: requiredNumber(cli, "scene", "duplicate-to-arrangement requires --scene", { integer: true, min: 0 }),
        startBeat: requiredNumber(cli, "start", "duplicate-to-arrangement requires --start", { min: 0 }),
      });
    case "write":
    case "smoke-write":
      return withClient(cli, {
        id: commandId("write"),
        type: "write_midi_clip",
        ...targetArgs,
        replaceExisting: hasFlag(cli, "replace"),
        clip: command === "smoke-write" ? smokeClip() : readClipArg(cli),
      });
    default:
      throw new ScriptError("unknown_command", `Unknown command: ${command}`, EXIT.INVALID_ARGS, { commands: [...COMMANDS].sort() });
  }
}

function requiredString(cli, name, message) {
  const value = stringFlag(cli, name, "");
  if (!value) throw new ScriptError("missing_required_flag", message, EXIT.INVALID_ARGS);
  return value;
}

function requiredNumber(cli, name, message, options = {}) {
  const value = numberFlag(cli, name, undefined, options);
  if (value == null) throw new ScriptError("missing_required_flag", message, EXIT.INVALID_ARGS);
  return value;
}

function buildClipStatusPayloads(cli) {
  const targetArgs = readTargetFlags(cli);
  const payloads = [];
  const name = stringFlag(cli, "name", "");
  const color = numberFlag(cli, "color", undefined, { integer: true, min: 0 });
  if (name) payloads.push(withClient(cli, { id: commandId("set-clip-name"), type: "set_clip_name", ...targetArgs, name }));
  if (color != null) payloads.push(withClient(cli, { id: commandId("set-clip-color"), type: "set_clip_color", ...targetArgs, color }));
  if (payloads.length === 0) {
    throw new ScriptError("missing_clip_status", "set-clip-status requires --name and/or --color", EXIT.INVALID_ARGS);
  }
  return payloads;
}

function commandHelp(command) {
  return {
    ok: true,
    script: "scripts/live-bridge.mjs",
    command,
    description: "Interact with the local ChordChemist Max for Live bridge.",
    prerequisites: ["Node.js 18+", `Bridge server reachable at ${DEFAULT_BRIDGE_URL}`, "Loaded ChordChemist Bridge.amxd for command dispatch"],
    environment: {
      CHORD_CHEMIST_LIVE_BRIDGE_URL: "Override bridge URL.",
      CHORDCHEMIST_LIVE_BRIDGE_URL: "Legacy override bridge URL.",
    },
    mutability: {
      readOnly: [...READ_ONLY_COMMANDS],
      statefulNonLiveMutations: [...STATEFUL_NON_LIVE_MUTATIONS],
      liveMutations: [...LIVE_MUTATIONS],
    },
    commonFlags: {
      "--help": "Show this help.",
      "--dry-run": "Print the HTTP route and bridge command payload without sending it.",
      "--compact": "Print compact JSON instead of pretty JSON.",
      "--wait-ms": "Bridge command wait in milliseconds. Default: 8000, write: 15000.",
      "--client": "Route to a specific M4L poller client id.",
    },
    selectedCommand: command && COMMAND_DETAILS[command] ? COMMAND_DETAILS[command] : undefined,
    targets: {
      "--target=highlighted_clip_slot": "Default target.",
      "--target=session_clip_slot --track=N --scene=N": "Explicit Session slot.",
      "--target=arrangement_clip --track=N --clip=N": "Existing Arrangement clip.",
      "--target=detail_clip": "Visible Clip View fallback.",
    },
    commands: {
      health: "GET /health.",
      state: "Read state for the target clip.",
      context: "Read observer-invalidated cached Live context.",
      audit: "Read bounded musical set audit.",
      read: "Read MIDI notes from a target clip.",
      write: "Write clip JSON from file or stdin to a target.",
      "smoke-write": "Write a built-in test chord clip.",
      "track-summary": "Read mixer/routing/device-aware track summaries.",
      "device-summary": "Read devices and exposed parameters for one track.",
      "rename-track": "Rename a track. Requires --track and --name.",
      "rename-scene": "Rename a Session scene. Requires --scene and --name.",
      "set-track": "Set mute/solo/arm/volume/pan with a snapshot.",
      "snapshot-mixer": "Save restorable mixer state.",
      "restore-mixer": "Restore a mixer snapshot.",
      "set-device-param": "Set one exposed device parameter with a snapshot.",
      "restore-device-param": "Restore a device parameter snapshot.",
      "set-clip-status": "Rename and/or recolor a target clip.",
      "watch-clip-requests": "Scan Session clips for cc: clip-name prompts.",
      "set-arrangement-end": "Set end time for an Arrangement clip.",
      "duplicate-to-arrangement": "Duplicate a Session clip to Arrangement.",
      fire: "Fire a clip slot target.",
      stop: "Stop a clip slot target.",
    },
    examples: [
      "scripts/live-bridge.mjs health",
      "scripts/live-bridge.mjs audit --tracks=8 --scenes=16 --notes=128",
      "scripts/live-bridge.mjs read --target=arrangement_clip --track=2 --clip=0",
      "scripts/live-bridge.mjs write ./clip.json --target=session_clip_slot --track=0 --scene=2 --replace --dry-run",
      "scripts/live-bridge.mjs set-track --track=2 --solo=true --dry-run",
      "scripts/live-bridge.mjs restore-mixer --snapshot=mixer-123",
    ],
    exitCodes: {
      0: "success",
      [EXIT.GENERAL]: "general runtime error",
      [EXIT.INVALID_ARGS]: "invalid arguments or malformed input",
      [EXIT.BRIDGE_UNREACHABLE]: "bridge HTTP server unreachable or returned HTTP error",
      [EXIT.BRIDGE_REJECTED]: "bridge returned ok=false for the command",
    },
  };
}

async function main() {
  const cli = parseCli(process.argv.slice(2));
  const command = cli.positionals[0] || "help";
  if (command === "help" || hasFlag(cli, "help") || command === "-h") {
    outputJson(commandHelp(command === "help" || command === "-h" ? undefined : command), cli);
    return;
  }
  if (!COMMANDS.has(command)) {
    throw new ScriptError("unknown_command", `Unknown command: ${command}`, EXIT.INVALID_ARGS, { commands: [...COMMANDS].sort() });
  }
  if (command === "health") {
    if (hasFlag(cli, "dry-run")) {
      outputJson({ ok: true, dryRun: true, request: { method: "GET", url: `${bridgeUrl}/health` } }, cli);
      return;
    }
    outputJson(await request("/health"), cli);
    return;
  }

  const waitMs = numberFlag(cli, "wait-ms", command === "write" || command === "smoke-write" ? 15000 : 8000, {
    integer: true,
    min: 1,
  });
  const payloads = command === "set-clip-status" ? buildClipStatusPayloads(cli) : [buildCommandPayload(command, cli)];

  if (hasFlag(cli, "dry-run")) {
    outputJson(
      {
        ok: true,
        dryRun: true,
        bridgeUrl,
        waitMs,
        mutability: READ_ONLY_COMMANDS.has(command)
          ? "read-only"
          : STATEFUL_NON_LIVE_MUTATIONS.has(command)
            ? "stateful-non-live"
            : "mutates-live",
        commands: payloads,
      },
      cli,
    );
    return;
  }

  const results = [];
  for (const payload of payloads) {
    results.push(await dispatch(payload, waitMs));
  }
  outputJson(results.length === 1 ? results[0] : { ok: results.every((item) => item.ok), results }, cli);
}

main().catch((error) => {
  const normalized =
    error instanceof ScriptError
      ? error
      : new ScriptError("script_error", error instanceof Error ? error.message : String(error), EXIT.GENERAL);
  errorJson(normalized);
  process.exit(normalized.exitCode);
});
