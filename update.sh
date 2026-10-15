#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"
if ! command -v git >/dev/null 2>&1; then echo "Git is required." >&2; exit 1; fi
if [ ! -d .git ]; then echo "This directory is not a Git checkout." >&2; exit 1; fi
if [ -n "$(git status --porcelain)" ]; then echo "Working tree has changes. Commit/stash them before updating; no files changed." >&2; exit 1; fi
PYTHON="$ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then echo "Run sh install.sh first." >&2; exit 1; fi
git fetch origin
git pull --ff-only origin main
"$PYTHON" -m pip install -r requirements.txt
"$PYTHON" -m pip check
"$PYTHON" -m compileall -q app.py terminal_ai.py agentic_features.py api_schemas.py command_control.py memory_store.py selfx_engine.py workspace_tools.py task_scheduler.py routers
"$PYTHON" -m pytest -q

if command -v systemctl >/dev/null 2>&1 && systemctl --user is-enabled terminal-ai.service >/dev/null 2>&1; then
  systemctl --user restart terminal-ai.service
  echo "Updated and restarted terminal-ai.service."
elif [ "$(uname -s)" = "Darwin" ] && command -v launchctl >/dev/null 2>&1 && [ -f "$HOME/Library/LaunchAgents/com.terminal-ai.server.plist" ]; then
  launchctl kickstart -k "gui/$(id -u)/com.terminal-ai.server"
  echo "Updated and restarted the Terminal AI LaunchAgent."
else
  echo "Update checks passed. Restart the running server to load the new code."
fi
