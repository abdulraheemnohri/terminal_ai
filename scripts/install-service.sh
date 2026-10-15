#!/usr/bin/env sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SERVICE_NAME=terminal-ai.service
TEMPLATE="$APP_DIR/deploy/systemd/terminal-ai.service"
TARGET="/etc/systemd/system/$SERVICE_NAME"
STATE_DIR="${TERMINAL_AI_STATE:-$HOME/.terminal_ai}"
PYTHON="$APP_DIR/.venv/bin/python"
[ "$(id -u)" -ne 0 ] || { echo "Run as normal user, not sudo." >&2; exit 1; }
[ -x "$PYTHON" ] || { echo "Run ./install.sh first." >&2; exit 1; }
command -v systemctl >/dev/null 2>&1 || { echo "systemd required." >&2; exit 1; }
command -v sudo >/dev/null 2>&1 || { echo "sudo required." >&2; exit 1; }
TMP=$(mktemp); trap 'rm -f "$TMP"' EXIT HUP INT TERM
sed -e "s|REPLACE_USER|$(id -un)|g" -e "s|REPLACE_APP_DIR|$APP_DIR|g" -e "s|REPLACE_STATE_DIR|$STATE_DIR|g" "$TEMPLATE" > "$TMP"
sudo install -m 0644 "$TMP" "$TARGET"
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
echo "Enabled at boot. Dashboard: http://127.0.0.1:8000"
echo "Status: sudo systemctl status $SERVICE_NAME"
echo "Logs: sudo journalctl -u $SERVICE_NAME -f"
echo "Disable: sudo systemctl disable --now $SERVICE_NAME"
