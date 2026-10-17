#!/usr/bin/env sh
# Safe, explicit update: clean git checkout -> fast-forward -> dependencies -> tests -> service restart.
# This script never runs automatically and never overwrites local source changes.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
[ -d .git ] || { echo "Run this from a Git checkout." >&2; exit 1; }
[ -x .venv/bin/python ] || { echo "Missing virtual environment; run sh install.sh first." >&2; exit 1; }
if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree has changes. Commit/stash them before updating." >&2
  exit 1
fi
echo "Fetching updates..."
git fetch --prune
BRANCH=$(git branch --show-current)
[ -n "$BRANCH" ] || { echo "Detached HEAD; checkout a branch first." >&2; exit 1; }
git merge-base --is-ancestor HEAD "origin/$BRANCH" || {
  echo "Update is not a fast-forward. No changes applied." >&2
  exit 1
}
if [ "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$BRANCH")" ]; then
  echo "Already up to date."
  exit 0
fi
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="$HOME/.terminal_ai/update-backups/$STAMP"
mkdir -p "$BACKUP"
git bundle create "$BACKUP/source.bundle" --all
PREVIOUS=$(git rev-parse HEAD)
UPDATED=0
rollback_update() {
  status=$?
  if [ "$status" -ne 0 ] && [ "$UPDATED" = "1" ]; then
    echo "Update failed; restoring source revision $PREVIOUS." >&2
    if git reset --hard "$PREVIOUS"; then
      if ! .venv/bin/python -m pip install -r requirements.txt; then
        echo "Warning: source rollback succeeded, but restoring the previous dependency set failed. Run .venv/bin/python -m pip install -r requirements.txt manually." >&2
      fi
    else
      echo "Warning: automatic source rollback failed. Restore commit $PREVIOUS manually." >&2
    fi
  fi
  exit "$status"
}
trap rollback_update EXIT
git merge --ff-only "origin/$BRANCH"
UPDATED=1
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m compileall -q app.py terminal_ai.py agent routers
.venv/bin/python -m pytest -q
if command -v systemctl >/dev/null 2>&1 && systemctl --user is-enabled terminal-ai.service >/dev/null 2>&1; then
  systemctl --user restart terminal-ai.service
elif command -v launchctl >/dev/null 2>&1 && [ -f "$HOME/Library/LaunchAgents/com.terminal-ai.server.plist" ]; then
  launchctl kickstart -k "gui/$(id -u)/com.terminal-ai.server"
else
  echo "Tests passed. No managed service found; restart the server manually."
fi
UPDATED=0
echo "Update complete. Source backup: $BACKUP/source.bundle"
