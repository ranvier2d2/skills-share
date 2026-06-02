#!/usr/bin/env bash
set -euo pipefail

find_repo_root() {
  local dir="$PWD"
  while [ "$dir" != "/" ]; do
    if [ -x "$dir/scripts/audit_roast.sh" ]; then
      printf "%s\n" "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

if ROOT="$(find_repo_root)"; then
  exec "$ROOT/scripts/audit_roast.sh" --root "$ROOT" "$@"
fi

cat <<'ERR' >&2
ERROR: scripts/audit_roast.sh not found.
Run this skill from within the repo tree so the repo-local script can be executed.
ERR

exit 2
