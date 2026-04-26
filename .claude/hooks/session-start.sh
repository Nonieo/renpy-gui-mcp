#!/usr/bin/env bash
# SessionStart hook for Claude Code on the web.
#
# Installs Python + frontend dependencies so pytest, ruff, and the Vite
# build are ready to run in the session. Idempotent — safe to re-run.

set -euo pipefail

# Only run in the remote (web) environment. Locally the contributor's own
# venv / npm setup is the source of truth.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# --- Python: editable install with dev + gui extras --------------------
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --quiet --upgrade pip
python -m pip install --quiet -e ".[dev,gui]"

# --- Frontend: npm install (cached layer benefits subsequent runs) -----
if [ -d gui/frontend ]; then
  (cd gui/frontend && npm install --no-audit --no-fund --loglevel=error)
fi

# --- Expose the venv to the rest of the session -----------------------
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export VIRTUAL_ENV=\"$CLAUDE_PROJECT_DIR/.venv\""
    echo "export PATH=\"$CLAUDE_PROJECT_DIR/.venv/bin:\$PATH\""
  } >> "$CLAUDE_ENV_FILE"
fi
