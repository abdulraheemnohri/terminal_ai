#!/usr/bin/env sh
# Opt-in weekly Terminal AI project updates for macOS.
# Updates the project only, not macOS system packages.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
[ -x "$ROOT/.venv/bin/python" ] || { echo "Run sh install.sh first." >&2; exit 1; }
[ -x "$ROOT/update.sh" ] || { echo "update.sh is missing." >&2; exit 1; }
command -v launchctl >/dev/null 2>&1 || { echo "launchctl is required on macOS." >&2; exit 1; }
LABEL="com.terminal-ai.auto-update"
AGENT_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs"
PLIST="$AGENT_DIR/$LABEL.plist"
mkdir -p "$AGENT_DIR" "$LOG_DIR"
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/sh</string><string>$ROOT/update.sh</string></array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>0</integer><key>Hour</key><integer>4</integer><key>Minute</key><integer>30</integer></dict>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$LOG_DIR/terminal-ai-update.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/terminal-ai-update-error.log</string>
</dict>
</plist>
EOF
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Weekly Terminal AI project updates enabled for Sunday 04:30 when this user is logged in."
echo "Logs: $LOG_DIR/terminal-ai-update.log and terminal-ai-update-error.log"
echo "Disable with: sh uninstall-auto-update-macos.sh"
echo "This runs update.sh from origin/main. Review the remote and keep backups before enabling."
