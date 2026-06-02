#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_subagent.sh <name> "<prompt>"

Environment:
  SUBAGENT_CWD       Working directory for codex exec (default: current directory)
  SUBAGENT_ROOT      Output directory (default: .codex/subagents)
  SUBAGENT_SANDBOX   read-only|workspace-write|danger-full-access (default: workspace-write)
  SUBAGENT_MODEL     Optional model override
  SUBAGENT_PROFILE   Optional codex profile override
  SUBAGENT_JSON      1 to enable --json and save JSONL events (default: 0)
  SUBAGENT_UNSAFE    1 to add --dangerously-bypass-approvals-and-sandbox (default: 0)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 2 ]]; then
  usage >&2
  exit 1
fi

name="$1"
shift
prompt="$*"

work_dir="${SUBAGENT_CWD:-$PWD}"
output_root="${SUBAGENT_ROOT:-.codex/subagents}"
sandbox_mode="${SUBAGENT_SANDBOX:-workspace-write}"
use_json="${SUBAGENT_JSON:-0}"
unsafe_mode="${SUBAGENT_UNSAFE:-0}"

mkdir -p "$output_root"

safe_name="$(printf '%s' "$name" | tr '[:space:]/' '__' | tr -cd '[:alnum:]_.-')"
if [[ -z "$safe_name" ]]; then
  safe_name="subagent"
fi

timestamp="$(date -u +"%Y%m%dT%H%M%SZ")"
message_file="${output_root}/${timestamp}_${safe_name}.md"
events_file="${output_root}/${timestamp}_${safe_name}.jsonl"

cmd=(codex exec -C "$work_dir" -s "$sandbox_mode" -o "$message_file")

if [[ -n "${SUBAGENT_MODEL:-}" ]]; then
  cmd+=(-m "$SUBAGENT_MODEL")
fi

if [[ -n "${SUBAGENT_PROFILE:-}" ]]; then
  cmd+=(-p "$SUBAGENT_PROFILE")
fi

if [[ "$use_json" == "1" ]]; then
  cmd+=(--json)
fi

if [[ "$unsafe_mode" == "1" ]]; then
  cmd+=(--dangerously-bypass-approvals-and-sandbox)
fi

cmd+=("$prompt")

echo "[subagent] name=$safe_name"
echo "[subagent] cwd=$work_dir"
echo "[subagent] output=$message_file"

if [[ "$use_json" == "1" ]]; then
  "${cmd[@]}" | tee "$events_file"
  echo "[subagent] events=$events_file"
else
  "${cmd[@]}"
fi

echo "[subagent] done"
