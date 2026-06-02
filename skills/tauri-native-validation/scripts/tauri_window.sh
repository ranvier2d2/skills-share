#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  tauri_window.sh info --app <AppName>
  tauri_window.sh capture --app <AppName> --x <num> --y <num> --width <num> --height <num> --out <path> [--settle <seconds>]

Commands:
  info      Print window name, position, and size for window 1.
  capture   Activate the app, move window 1, resize it, wait briefly, then capture the specified region.
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

command_name=$1
shift

app=""
x=220
y=80
width=1280
height=860
settle=1
out=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app)
      app=$2
      shift 2
      ;;
    --x)
      x=$2
      shift 2
      ;;
    --y)
      y=$2
      shift 2
      ;;
    --width)
      width=$2
      shift 2
      ;;
    --height)
      height=$2
      shift 2
      ;;
    --out)
      out=$2
      shift 2
      ;;
    --settle)
      settle=$2
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$app" ]]; then
  echo "--app is required" >&2
  exit 1
fi

case "$command_name" in
  info)
    osascript <<APPLESCRIPT
tell application "$app" to activate
delay 0.2
tell application "System Events"
  tell application process "$app"
    set frontmost to true
    return {name of window 1, position of window 1, size of window 1}
  end tell
end tell
APPLESCRIPT
    ;;
  capture)
    if [[ -z "$out" ]]; then
      echo "--out is required for capture" >&2
      exit 1
    fi
    mkdir -p "$(dirname "$out")"
    osascript <<APPLESCRIPT
tell application "$app" to activate
delay 0.3
tell application "System Events"
  tell application process "$app"
    set frontmost to true
    set position of window 1 to {$x, $y}
    set size of window 1 to {$width, $height}
  end tell
end tell
APPLESCRIPT
    sleep "$settle"
    screencapture -R${x},${y},${width},${height} "$out"
    printf '%s\n' "$out"
    ;;
  *)
    echo "Unknown command: $command_name" >&2
    usage
    exit 1
    ;;
esac
