#!/usr/bin/env sh
# Remove Terminal AI's per-user macOS LaunchAgent without deleting user data.
set -eu
if [ "$(uname -s)" != "Darwin" ]; then
  echo "This uninstaller is for macOS only." >&2
  exit 1
fi
PLIST="$HOME/Library/LaunchAgents/com.terminal-ai.server.plist"
DOMAIN="gui/$(id -u)"
launchctl bootout "$DOMAIN" "$PLIST" >/dev/null 2>&1 || true
if [ -f "$PLIST" ]; then
  rm -- "$PLIST"
  echo "Removed $PLIST"
else
  echo "LaunchAgent plist was already absent."
fi
echo "Logs and application state were left untouched."
