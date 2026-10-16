#!/usr/bin/env sh
set -eu
LABEL="com.terminal-ai.auto-update"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"
echo "Weekly Terminal AI project updates disabled. Project files and local data were kept."
