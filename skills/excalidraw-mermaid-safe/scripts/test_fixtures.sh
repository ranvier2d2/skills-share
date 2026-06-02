#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SKILL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
INPUT_DIR="$SKILL_DIR/assets/fixtures/input"
EXPECTED_DIR="$SKILL_DIR/assets/fixtures/expected"
TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/excalidraw-mermaid-safe-fixtures.XXXXXX")

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

VALIDATE_MODE="static"
if [[ "${1:-}" == "--strict" ]]; then
  VALIDATE_MODE="excalidraw-strict"
fi

run_case() {
  local input_name=$1
  local expected_name=$2
  local mode=$3
  local output="$TMP_DIR/$expected_name"

  "$SCRIPT_DIR/excali_mermaid_safe.sh" \
    --input "$INPUT_DIR/$input_name" \
    --output "$output" \
    --mode "$mode" \
    --palette safe \
    --layout grouped \
    --validate "$VALIDATE_MODE"

  diff -u "$EXPECTED_DIR/$expected_name" "$output"
}

run_case "outline-basic.md" "outline-basic.mmd" "from-markdown"
run_case "broken-links.md" "broken-links-fixed.mmd" "auto"
run_case "messy-markdown.md" "messy-markdown.mmd" "from-markdown"
run_case "complex-mermaid.md" "complex-mermaid-fixed.mmd" "auto"
run_case "long-labels.md" "long-labels.mmd" "from-markdown"

for fixture in "$EXPECTED_DIR"/*.mmd; do
  test -f "$fixture" || continue
done

echo "Fixture regression tests passed with --validate $VALIDATE_MODE"
