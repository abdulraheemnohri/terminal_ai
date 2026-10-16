#!/usr/bin/env sh
# Register Terminal AI to start at the current macOS user's login.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON="$ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then echo "Virtual environment not found. Run sh install.sh first." >&2; exit 1; fi
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST="$PLIST_DIR/com.terminal-ai.server.plist"
mkdir -p "$PLIST_DIR"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.terminal-ai.server</string>
  <key>ProgramArguments</key>
  <array><string>$PYTHON</string><string>-m</string><string>uvicorn</string><string>app:app</string><string>--host</string><string>127.0.0.1</string><string>--port</string><string>8000</string></array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/terminal-ai.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/terminal-ai-error.log</string>
</dict>
</plist>
EOF
mkdir -p "$HOME/Library/Logs"
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Terminal AI login startup enabled. Dashboard: http://127.0.0.1:8000"
echo "Remove it with: sh uninstall-launchagent.sh"
