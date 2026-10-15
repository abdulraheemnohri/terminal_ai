#!/usr/bin/env sh
# Install a user-level auto-start entry for Linux/WSL or Termux.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON="$ROOT/.venv/bin/python"
PORT="${TERMINAL_AI_PORT:-8000}"
HOST="${TERMINAL_AI_HOST:-127.0.0.1}"

if [ ! -x "$PYTHON" ]; then echo "Missing $PYTHON. Run ./install.sh first." >&2; exit 1; fi

if [ -n "${TERMUX_VERSION:-}" ] && [ -n "${PREFIX:-}" ]; then
  BOOT_DIR="$HOME/.termux/boot"
  mkdir -p "$BOOT_DIR" "$HOME/.terminal_ai/logs"
  cat > "$BOOT_DIR/terminal-ai" <<EOF
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock >/dev/null 2>&1 || true
cd "$ROOT" || exit 1
mkdir -p "$HOME/.terminal_ai/logs"
nohup "$PYTHON" -m uvicorn app:app --host "$HOST" --port "$PORT" >> "$HOME/.terminal_ai/logs/server.log" 2>&1 &
EOF
  chmod 700 "$BOOT_DIR/terminal-ai"
  echo "Installed Termux:Boot startup script: $BOOT_DIR/terminal-ai"
  echo "Install and open the Termux:Boot app, then reboot to test."
  echo "Server: http://$HOST:$PORT"
  exit 0
fi

command -v systemctl >/dev/null 2>&1 || { echo "systemctl not found. On Termux use Termux:Boot; otherwise configure your init system manually." >&2; exit 1; }
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"
cat > "$UNIT_DIR/terminal-ai.service" <<EOF
[Unit]
Description=Terminal AI local-first agent web server
After=network.target

[Service]
Type=simple
WorkingDirectory=$ROOT
Environment=PYTHONUNBUFFERED=1
ExecStart=$PYTHON -m uvicorn app:app --host $HOST --port $PORT
Restart=always
RestartSec=5
TimeoutStopSec=20
KillSignal=SIGINT
UMask=0077

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now terminal-ai.service
if command -v loginctl >/dev/null 2>&1; then
  loginctl enable-linger "$(id -un)" >/dev/null 2>&1 || echo "Optional: sudo loginctl enable-linger $(id -un)"
fi
echo "Installed and started terminal-ai.service."
echo "Status: systemctl --user status terminal-ai.service"
echo "Logs: journalctl --user -u terminal-ai.service -f"
echo "Stop: systemctl --user disable --now terminal-ai.service"
echo "Server: http://$HOST:$PORT"
