#!/usr/bin/env bash
# Dev mode: backend on :8765 with the API only, Vite dev server on :5173 with
# hot-reload. Vite proxies /api and /ws through to the backend.
#
# Usage:
#   gui/dev.sh <project-path> <sdk-path>

set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "usage: $0 <project-path> <sdk-path>" >&2
    exit 2
fi

PROJECT="$1"
SDK="$2"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$REPO_ROOT/.venv/bin/python}"

cleanup() { kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

# Backend (no static-dir; Vite serves the SPA in dev).
"$PYTHON" -m renpy_mcp_gui \
    --project "$PROJECT" \
    --sdk "$SDK" \
    --no-browser &

# Vite dev server.
(cd "$REPO_ROOT/gui/frontend" && npm install && npm run dev) &

wait
