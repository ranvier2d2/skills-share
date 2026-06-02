#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_subagent_batch.sh <tasks.tsv>

TSV format:
  name<TAB>prompt<TAB>cwd(optional)

Environment:
  SUBAGENT_BATCH_MODE  serial|parallel (default: serial)
  Any env var supported by run_subagent.sh is also supported.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 1
fi

tasks_file="$1"
if [[ ! -f "$tasks_file" ]]; then
  echo "tasks file not found: $tasks_file" >&2
  exit 1
fi

batch_mode="${SUBAGENT_BATCH_MODE:-serial}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runner="${script_dir}/run_subagent.sh"

if [[ ! -x "$runner" ]]; then
  chmod +x "$runner"
fi

run_one() {
  local task_name="$1"
  local task_prompt="$2"
  local task_cwd="$3"

  if [[ -n "$task_cwd" ]]; then
    SUBAGENT_CWD="$task_cwd" "$runner" "$task_name" "$task_prompt"
  else
    "$runner" "$task_name" "$task_prompt"
  fi
}

status=0
pids=""

while IFS=$'\t' read -r task_name task_prompt task_cwd || [[ -n "${task_name:-}" ]]; do
  [[ -z "${task_name:-}" ]] && continue
  [[ "${task_name:0:1}" == "#" ]] && continue
  [[ -z "${task_prompt:-}" ]] && {
    echo "Skipping '$task_name': missing prompt" >&2
    status=1
    continue
  }

  if [[ "$batch_mode" == "parallel" ]]; then
    run_one "$task_name" "$task_prompt" "${task_cwd:-}" &
    pids="$pids $!"
  else
    if ! run_one "$task_name" "$task_prompt" "${task_cwd:-}"; then
      status=1
    fi
  fi
done < "$tasks_file"

if [[ "$batch_mode" == "parallel" ]]; then
  for pid in $pids; do
    if ! wait "$pid"; then
      status=1
    fi
  done
fi

exit "$status"
