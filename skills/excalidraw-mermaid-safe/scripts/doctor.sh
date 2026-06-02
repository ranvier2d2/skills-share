#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "Checking required runtime..."
command -v python3 >/dev/null 2>&1 || {
  echo "error: python3 not found" >&2
  exit 1
}
python3 --version

echo "Running static fixture regression tests..."
"$SCRIPT_DIR/test_fixtures.sh"

echo "Checking optional strict parser runtime..."
if command -v node >/dev/null 2>&1 && [[ -d "$SCRIPT_DIR/node_modules/@excalidraw/mermaid-to-excalidraw" ]]; then
  node --version
  "$SCRIPT_DIR/test_fixtures.sh" --strict
else
  echo "Optional strict parser validation unavailable. Run scripts/bootstrap.sh to install it."
fi

echo "Doctor checks completed."
