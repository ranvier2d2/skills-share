#!/usr/bin/env bash
set -euo pipefail

EXIT_GENERAL=1
EXIT_INVALID_ARGS=2

known_repo="${CHORDCHEMIST_REPO:-}"
repo="${CHORDCHEMIST_M4L_REPO:-${CHORDCHEMIST_REPO:-}}"
app_url="http://localhost:8080"
bridge_url="http://127.0.0.1:53873"
json_output=0

usage() {
  cat <<'EOF'
Usage: scripts/check-stack.sh [OPTIONS]

Check local ChordChemist/Ableton/M4L readiness without printing secrets.

Options:
  --repo PATH          ChordChemist M4L repo. Defaults to current repo discovery or known local worktree.
  --app-url URL        Local app base URL. Default: http://localhost:8080
  --bridge-url URL     Local Live bridge URL. Default: http://127.0.0.1:53873
  --json               Print machine-readable JSON.
  --help               Show this help.

Environment:
  CHORDCHEMIST_M4L_REPO / CHORDCHEMIST_REPO can provide the repo path.

Exit codes:
  0 success
  1 general runtime error
  2 invalid arguments

Examples:
  scripts/check-stack.sh
  scripts/check-stack.sh --json
  scripts/check-stack.sh --repo /path/to/chord-chemist --bridge-url http://127.0.0.1:53873
EOF
}

die_args() {
  printf '{"ok":false,"error":"invalid_arguments","message":%s}\n' "$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1")" >&2
  exit "$EXIT_INVALID_ARGS"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --json)
      json_output=1
      shift
      ;;
    --repo)
      [[ $# -ge 2 ]] || die_args "--repo requires a path"
      repo="$2"
      shift 2
      ;;
    --repo=*)
      repo="${1#--repo=}"
      shift
      ;;
    --app-url)
      [[ $# -ge 2 ]] || die_args "--app-url requires a URL"
      app_url="$2"
      shift 2
      ;;
    --app-url=*)
      app_url="${1#--app-url=}"
      shift
      ;;
    --bridge-url)
      [[ $# -ge 2 ]] || die_args "--bridge-url requires a URL"
      bridge_url="$2"
      shift 2
      ;;
    --bridge-url=*)
      bridge_url="${1#--bridge-url=}"
      shift
      ;;
    *)
      if [[ -z "$repo" && -d "$1" ]]; then
        repo="$1"
        shift
      else
        die_args "Unknown argument: $1"
      fi
      ;;
  esac
done

if [[ -z "$repo" ]]; then
  cwd="$PWD"
  while [[ "$cwd" != "/" ]]; do
    if [[ -f "$cwd/package.json" && -d "$cwd/m4l/chord-chemist-bridge" ]]; then
      repo="$cwd"
      break
    fi
    cwd="$(dirname "$cwd")"
  done
fi

if [[ -z "$repo" && -n "$known_repo" && -d "$known_repo" ]]; then
  repo="$known_repo"
fi

say() {
  printf '%-24s %s\n' "$1" "$2"
}

present_line() {
  local file="$1"
  local key="$2"
  [[ -f "$file" ]] && grep -q "^${key}=" "$file"
}

curl_json() {
  local url="$1"
  curl -fsS --max-time 2 "$url" 2>/dev/null || true
}

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"
}

bool_json() {
  [[ "$1" == "true" ]] && printf 'true' || printf 'false'
}

repo_present=false
branch="unknown"
env_present=false
openai_key_present=false
elevenlabs_key_present=false
if [[ -n "$repo" && -d "$repo" ]]; then
  repo_present=true
  branch="$(git -C "$repo" branch --show-current 2>/dev/null || echo unknown)"
  if [[ -f "$repo/.env" ]]; then
    env_present=true
    present_line "$repo/.env" "OPENAI_API_KEY" && openai_key_present=true
    present_line "$repo/.env" "ELEVENLABS_API_KEY" && elevenlabs_key_present=true
  fi
fi

local_status="$(curl_json "$app_url/api/local/status")"
app_responding=false
openai_ok="null"
sqlite_ok="null"
sqlite_db_path=""
scribe_ok="null"
if [[ -n "$local_status" ]]; then
  app_responding=true
parsed_local="$(STATUS_JSON="$local_status" python3 - <<'PY' || true
import json, os
try:
    data = json.loads(os.environ["STATUS_JSON"])
except Exception:
    data = {}
print(json.dumps(data.get("openai", {}).get("ok")))
print(json.dumps(data.get("sqlite", {}).get("ok")))
print(data.get("sqlite", {}).get("dbPath") or "")
print(json.dumps(data.get("scribe", {}).get("ok")))
PY
)"
  openai_ok="$(printf '%s\n' "$parsed_local" | sed -n '1p')"
  sqlite_ok="$(printf '%s\n' "$parsed_local" | sed -n '2p')"
  sqlite_db_path="$(printf '%s\n' "$parsed_local" | sed -n '3p')"
  scribe_ok="$(printf '%s\n' "$parsed_local" | sed -n '4p')"
fi

bridge_status="$(curl_json "$bridge_url/health")"
bridge_responding=false
queued_commands="null"
waiting_pollers="null"
if [[ -n "$bridge_status" ]]; then
  bridge_responding=true
parsed_bridge="$(STATUS_JSON="$bridge_status" python3 - <<'PY' || true
import json, os
try:
    data = json.loads(os.environ["STATUS_JSON"])
except Exception:
    data = {}
payload = data.get("data", {})
print(json.dumps(payload.get("queuedCommands")))
print(json.dumps(payload.get("waitingPollers")))
PY
)"
  queued_commands="$(printf '%s\n' "$parsed_bridge" | sed -n '1p')"
  waiting_pollers="$(printf '%s\n' "$parsed_bridge" | sed -n '2p')"
fi

amxd="$HOME/Music/Ableton/User Library/Presets/MIDI Effects/Max MIDI Effect/ChordChemist Bridge.amxd"
max_node="$HOME/Documents/Max 8/Library/chord-chemist-m4l-client-http.js"
max_js="$HOME/Documents/Max 8/Library/live-api-bridge.js"
m4l_device_present="$([[ -f "$amxd" ]] && echo true || echo false)"
max_node_present="$([[ -f "$max_node" ]] && echo true || echo false)"
max_js_present="$([[ -f "$max_js" ]] && echo true || echo false)"
max_node_sync="unknown"
max_js_sync="unknown"

if [[ "$repo_present" == true ]]; then
  if [[ -f "$max_node" && -f "$repo/m4l/chord-chemist-bridge/node_content/chord-chemist-m4l-client-http.js" ]]; then
    if cmp -s "$max_node" "$repo/m4l/chord-chemist-bridge/node_content/chord-chemist-m4l-client-http.js"; then
      max_node_sync="matches repo"
    else
      max_node_sync="differs from repo"
    fi
  fi
  if [[ -f "$max_js" && -f "$repo/m4l/chord-chemist-bridge/max-js/live-api-bridge.js" ]]; then
    if cmp -s "$max_js" "$repo/m4l/chord-chemist-bridge/max-js/live-api-bridge.js"; then
      max_js_sync="matches repo"
    else
      max_js_sync="differs from repo"
    fi
  fi
fi

ableton_running=false
if pgrep -f "Ableton Live" >/dev/null 2>&1; then
  ableton_running=true
fi

if [[ "$json_output" -eq 1 ]]; then
  cat <<EOF
{
  "ok": true,
  "repo": {
    "path": $(json_escape "${repo:-}"),
    "present": $(bool_json "$repo_present"),
    "branch": $(json_escape "$branch"),
    "envPresent": $(bool_json "$env_present"),
    "openaiApiKeyPresent": $(bool_json "$openai_key_present"),
    "elevenlabsApiKeyPresent": $(bool_json "$elevenlabs_key_present")
  },
  "app": {
    "url": $(json_escape "$app_url"),
    "responding": $(bool_json "$app_responding"),
    "openaiOk": $openai_ok,
    "sqliteOk": $sqlite_ok,
    "sqliteDbPath": $(json_escape "$sqlite_db_path"),
    "scribeOk": $scribe_ok
  },
  "bridge": {
    "url": $(json_escape "$bridge_url"),
    "responding": $(bool_json "$bridge_responding"),
    "queuedCommands": $queued_commands,
    "waitingPollers": $waiting_pollers
  },
  "ableton": {
    "running": $(bool_json "$ableton_running"),
    "m4lDevicePresent": $m4l_device_present,
    "maxNodeClientPresent": $max_node_present,
    "maxLiveApiJsPresent": $max_js_present,
    "maxNodeSync": $(json_escape "$max_node_sync"),
    "maxJsSync": $(json_escape "$max_js_sync")
  }
}
EOF
  exit 0
fi

say "repo" "${repo:-missing}"
if [[ "$repo_present" == true ]]; then
  say "git branch" "$branch"
  say ".env" "$([[ "$env_present" == true ]] && echo present || echo missing)"
  say "OPENAI_API_KEY" "$([[ "$openai_key_present" == true ]] && echo present || echo missing)"
  say "ELEVENLABS_API_KEY" "$([[ "$elevenlabs_key_present" == true ]] && echo present || echo missing)"
else
  say "repo check" "not found"
fi

if [[ "$app_responding" == true ]]; then
  say "app" "$app_url responding"
  say "openai.ok" "$openai_ok"
  say "sqlite.ok" "$sqlite_ok"
  say "sqlite.dbPath" "$sqlite_db_path"
  say "scribe.ok" "$scribe_ok"
else
  say "app" "$app_url not responding"
fi

if [[ "$bridge_responding" == true ]]; then
  say "live bridge" "$bridge_url responding"
  say "queuedCommands" "$queued_commands"
  say "waitingPollers" "$waiting_pollers"
else
  say "live bridge" "$bridge_url not responding"
fi

say "M4L device" "$([[ "$m4l_device_present" == true ]] && echo present || echo missing)"
say "Max node client" "$([[ "$max_node_present" == true ]] && echo present || echo missing)"
say "Max LiveAPI js" "$([[ "$max_js_present" == true ]] && echo present || echo missing)"
say "Max node sync" "$max_node_sync"
say "Max js sync" "$max_js_sync"
say "Ableton Live" "$([[ "$ableton_running" == true ]] && echo running || echo "not running")"
