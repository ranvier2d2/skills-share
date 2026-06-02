#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
bootstrap_direnv.sh — ensure .envrc exists, run `direnv allow`, and load env

Usage:
  bootstrap_direnv.sh [--root DIR] [--config-slug SLUG] [--force-envrc]

Notes:
  - Intended for one-time setup in a new worktree.
  - Uses `direnv export bash` so it can be sourced from bash/zsh:
      source ./bootstrap_direnv.sh
    or:
      . ./bootstrap_direnv.sh
EOF
}

ROOT=""
CONFIG_SLUG="medicalassistant_mcp"
FORCE_ENVRC="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="${2:-}"; shift 2;;
    --config-slug)
      CONFIG_SLUG="${2:-}"; shift 2;;
    --force-envrc)
      FORCE_ENVRC="1"; shift;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$ROOT" ]]; then
  ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi
cd "$ROOT" || exit 1

if ! command -v direnv >/dev/null 2>&1; then
  echo "Error: direnv not found. Install it (brew install direnv / apt install direnv) and retry." >&2
  exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

if [[ ! -f "$ROOT/.envrc" || "$FORCE_ENVRC" == "1" ]]; then
  if [[ "$FORCE_ENVRC" == "1" ]]; then
    bash "$SCRIPT_DIR/write_envrc.sh" --root "$ROOT" --config-slug "$CONFIG_SLUG" --force
  else
    bash "$SCRIPT_DIR/write_envrc.sh" --root "$ROOT" --config-slug "$CONFIG_SLUG"
  fi
fi

direnv allow . >/dev/null
eval "$(direnv export bash)"
echo "✓ direnv allowed and environment loaded for: $ROOT"
