#!/usr/bin/env sh
set -eu
PLIST="$HOME/Library/LaunchAgents/com.terminal-ai.server.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"
echo "Terminal AI login startup removed. Project files and data were kept."
