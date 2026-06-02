#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

if ! command -v pnpm >/dev/null 2>&1; then
  echo "error: pnpm not found. Install pnpm before bootstrapping strict parser validation." >&2
  exit 1
fi

cd "$SCRIPT_DIR"
pnpm install

echo "Installed optional Excalidraw parser dependencies in $SCRIPT_DIR"
