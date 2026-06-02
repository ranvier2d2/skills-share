#!/bin/bash
# SessionEnd hook wrapper for flashback out-of-band analyzer.
#
# Receives JSON on stdin from Claude Code's SessionEnd event:
#   {"session_id": "...", "transcript_path": "...", "cwd": "...", "reason": "..."}
#
# Skips trivial sessions (reason=clear or very small transcripts).
# Invokes flashback_analyzer.py with --no-llm for speed (async hook).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
REASON=$(echo "$INPUT" | jq -r '.reason // empty')

# Skip trivial sessions
if [ "$REASON" = "clear" ]; then
    exit 0
fi

# Skip if transcript doesn't exist or is empty
if [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; then
    exit 0
fi

# Skip tiny sessions (< 5 lines = likely just a greeting or test)
LINE_COUNT=$(wc -l < "$TRANSCRIPT" 2>/dev/null || echo "0")
if [ "$LINE_COUNT" -lt 5 ]; then
    exit 0
fi

# Run the analyzer (heuristic-only for speed in hook context)
python3 "$SCRIPT_DIR/flashback_analyzer.py" \
    --transcript "$TRANSCRIPT" \
    --repo-root "${CWD:-.}" \
    --no-llm \
    >> "${CWD}/output/flashback/hook.log" 2>&1 || true

exit 0
