#!/usr/bin/env sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$APP_DIR"
PYTHON="$APP_DIR/.venv/bin/python"
BRANCH="${TERMINAL_AI_UPDATE_BRANCH:-main}"
STATE_DIR="${TERMINAL_AI_STATE:-$HOME/.terminal_ai}"
SERVICE_NAME=terminal-ai.service
[ -x "$PYTHON" ] || { echo "Run ./install.sh first." >&2; exit 1; }
if ! git diff --quiet || ! git diff --cached --quiet; then echo "Refusing update: tracked files have local changes." >&2; exit 1; fi
mkdir -p "$STATE_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
tar -czf "$STATE_DIR/pre-update-$STAMP.tar.gz" -C "$STATE_DIR" --exclude="pre-update-*.tar.gz" . || { echo "State backup failed; stopping." >&2; exit 1; }
git fetch origin "$BRANCH"
git merge --ff-only "origin/$BRANCH"
"$PYTHON" -m pip install -r requirements.txt
"$PYTHON" -m pip check
"$PYTHON" -m py_compile app.py terminal_ai.py litert_api_backend.py api_provider_backend.py
if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then sudo systemctl restart "$SERVICE_NAME"; sudo systemctl --no-pager --full status "$SERVICE_NAME"; else echo "Update installed. Restart the manually launched server."; fi
echo "Update complete. State backup: $STATE_DIR/pre-update-$STAMP.tar.gz"
