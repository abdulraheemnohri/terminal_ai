#!/usr/bin/env sh
# Install a per-user startup service for Terminal AI on Linux/macOS.
# Run from any directory: sh scripts/install-service.sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "Missing .venv/bin/python. Run sh install.sh first." >&2
  exit 1
fi
PYTHON="$ROOT/.venv/bin/python"
HOST="${TERMINAL_AI_HOST:-127.0.0.1}"
PORT="${TERMINAL_AI_PORT:-8000}"
case "$PORT" in *[!0-9]*|'') echo "TERMINAL_AI_PORT must be numeric." >&2; exit 1;; esac
if [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then echo "Port must be 1–65535." >&2; exit 1; fi

case "$(uname -s)" in
  Linux)
    command -v systemctl >/dev/null 2>&1 || { echo "systemd is required for this installer." >&2; exit 1; }
    SERVICE_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
    mkdir -p "$SERVICE_DIR"
    cat > "$SERVICE_DIR/terminal-ai.service" <<EOF
[Unit]
Description=Terminal AI local agent web server
After=network.target

[Service]
Type=simple
WorkingDirectory=$ROOT
Environment=PYTHONUNBUFFERED=1
Environment=TERMINAL_AI_HOST=$HOST
Environment=TERMINAL_AI_PORT=$PORT
ExecStart=$PYTHON -m uvicorn app:app --host $HOST --port $PORT
Restart=on-failure
RestartSec=5
TimeoutStopSec=20
NoNewPrivileges=true
UMask=0077

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable --now terminal-ai.service
    echo "Installed and started terminal-ai.service."
    echo "Status: systemctl --user status terminal-ai.service"
    echo "Logs:   journalctl --user -u terminal-ai.service -f"
    echo "Stop:   systemctl --user disable --now terminal-ai.service"
    if [ "${TERMINAL_AI_ENABLE_LINGER:-0}" = "1" ]; then
      if command -v loginctl >/dev/null 2>&1; then
        loginctl enable-linger "$USER" || echo "Could not enable lingering; service starts at user login." >&2
      else
        echo "loginctl unavailable; service starts at user login." >&2
      fi
    else
      echo "Starts at user login. For boot-before-login, set TERMINAL_AI_ENABLE_LINGER=1 and rerun (system policy may require admin approval)."
    fi
    ;;
  Darwin)
    SERVICE_DIR="$HOME/Library/LaunchAgents"
    mkdir -p "$SERVICE_DIR"
    PLIST="$SERVICE_DIR/com.terminal-ai.server.plist"
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.terminal-ai.server</string>
<key>ProgramArguments</key><array><string>$PYTHON</string><string>-m</string><string>uvicorn</string><string>app:app</string><string>--host</string><string>$HOST</string><string>--port</string><string>$PORT</string></array>
<key>WorkingDirectory</key><string>$ROOT</string>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>$HOME/Library/Logs/terminal-ai.log</string>
<key>StandardErrorPath</key><string>$HOME/Library/Logs/terminal-ai-error.log</string>
<key>Umask</key><integer>63</integer>
</dict></plist>
EOF
    mkdir -p "$HOME/Library/Logs"
    launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    echo "Installed launch agent; it starts at user login and restarts if it exits."
    echo "Stop/unload: launchctl bootout gui/$(id -u) $PLIST"
    ;;
  *)
    echo "Unsupported OS. Use systemd on Linux or launchd on macOS; Termux needs Termux:Boot." >&2
    exit 1
    ;;
esac
