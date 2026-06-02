#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash scripts/codex_env_clipboard.sh
#   OVERWRITE=1 bash scripts/codex_env_clipboard.sh
#   CONFIG_SLUG=my_app bash scripts/codex_env_clipboard.sh
#
# Writes:
#   - ./.envrc
#   - ./codex_setup_script.sh
#
# Also copies the Codex setup script to clipboard when possible.

OVERWRITE="${OVERWRITE:-0}"
CONFIG_SLUG="${CONFIG_SLUG:-}"

repo_root() {
  git rev-parse --show-toplevel 2>/dev/null || pwd
}

copy_to_clipboard() {
  if command -v pbcopy >/dev/null 2>&1; then pbcopy; return 0; fi
  if command -v wl-copy >/dev/null 2>&1; then wl-copy; return 0; fi
  if command -v xclip >/dev/null 2>&1; then xclip -selection clipboard; return 0; fi
  if command -v xsel >/dev/null 2>&1; then xsel --clipboard --input; return 0; fi
  if command -v clip.exe >/dev/null 2>&1; then clip.exe; return 0; fi
  return 1
}

write_file() {
  local path="$1"
  local content="$2"
  if [[ -f "$path" && "$OVERWRITE" != "1" ]]; then
    echo "• Skipping existing: $path (set OVERWRITE=1 to overwrite)"
    return 0
  fi
  umask 077
  printf "%s\n" "$content" > "$path"
  echo "✓ Wrote: $path"
}

ROOT="$(repo_root)"
PROJECT="$(basename "$ROOT")"
cd "$ROOT" || exit 1

if [[ -z "$CONFIG_SLUG" ]]; then
  CONFIG_SLUG="$PROJECT"
fi

ENVRC_PATH="$ROOT/.envrc"
SETUP_PATH="$ROOT/codex_setup_script.sh"

GENERIC_ENVRC_CONTENT="$(cat <<EOF
# Generic direnv bootstrap for git worktrees (dev local)
# - Seeds .env from ~/.config/${CONFIG_SLUG}/.env if missing
# - Fallback: copy from another worktree that has .env (even if gitignored)
# - Loads variables if .env exists

ROOT="\$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "\$ROOT" || exit 1

ENV_FILE="\$ROOT/.env"
SRC_CFG="\${HOME}/.config/${CONFIG_SLUG}/.env"

if [[ ! -f "\$ENV_FILE" ]]; then
  umask 077

  if [[ -f "\$SRC_CFG" ]]; then
    cat "\$SRC_CFG" > "\$ENV_FILE"
    echo "✓ Seeded .env from \$SRC_CFG"
  else
    CUR="\$ROOT"
    if command -v git >/dev/null 2>&1; then
      while IFS= read -r WT; do
        [[ -n "\$WT" ]] || continue
        [[ "\$WT" == "\$CUR" ]] && continue
        if [[ -f "\$WT/.env" ]]; then
          cat "\$WT/.env" > "\$ENV_FILE"
          echo "✓ Seeded .env from worktree: \$WT/.env"
          break
        fi
      done < <(git worktree list --porcelain 2>/dev/null | awk '\$1=="worktree"{print \$2}')
    fi
  fi
fi

if type -t dotenv_if_exists >/dev/null 2>&1; then
  dotenv_if_exists "\$ENV_FILE"
elif type -t dotenv >/dev/null 2>&1; then
  [[ -f "\$ENV_FILE" ]] && dotenv "\$ENV_FILE"
fi
EOF
)"

SETUP_SCRIPT_CONTENT="$(cat <<EOF
#!/usr/bin/env bash
set -euo pipefail

cd "\${WORKTREE_ROOT:-\$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
echo "→ setup in: \$(pwd)"

if [ ! -f .envrc ]; then
  cat > .envrc <<'ENVRC_EOF'
$GENERIC_ENVRC_CONTENT
ENVRC_EOF
  echo "✓ Wrote .envrc"
fi

if ! command -v direnv >/dev/null 2>&1; then
  echo "Error: direnv not found. Install it (brew install direnv / apt install direnv) and retry."
  exit 1
fi

direnv allow .

# Run inside the direnv environment (NO eval/export -> avoids leaking secrets in logs)
direnv exec . bash -lc '
  set -euo pipefail

  if [ -f .env ]; then
    echo "✓ .env present"
  else
    echo "⚠️ .env missing (expected ~/.config/${CONFIG_SLUG}/.env)"
  fi

  # --- install dependencies (edit to taste) ---
  uv sync
'
EOF
)"

write_file "$ENVRC_PATH" "$GENERIC_ENVRC_CONTENT"
write_file "$SETUP_PATH" "$SETUP_SCRIPT_CONTENT"
chmod +x "$SETUP_PATH" 2>/dev/null || true

if printf "%s\n" "$SETUP_SCRIPT_CONTENT" | copy_to_clipboard; then
  echo "✓ Copied setup script to clipboard (paste into Codex Environment → Setup script)"
else
  echo "⚠️ No clipboard tool found (pbcopy/wl-copy/xclip/xsel/clip.exe)."
  echo "  Setup script saved at: $SETUP_PATH"
fi

echo
echo "Done."
echo "Repo .envrc: $ENVRC_PATH"
echo "Setup script: $SETUP_PATH"
echo "Canonical env (recommended): \$HOME/.config/${CONFIG_SLUG}/.env"
