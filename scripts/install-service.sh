#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON="$ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then echo "Virtual environment not found. Run sh install.sh first." >&2; exit 1; fi
if ! command -v systemctl >/dev/null 2>&1; then echo "systemd is not available. Use start-server.sh or your OS service manager." >&2; exit 1; fi
SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"
cat > "$SERVICE_DIR/terminal-ai.service" <<EOF
[Unit]
Description=Terminal AI local web agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT
Environment=PYTHONUNBUFFERED=1
ExecStart=$PYTHON -m uvicorn app:app --host 127.0.0.1 --port 8000
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
echo "Service enabled: systemctl --user status terminal-ai.service"
echo "Dashboard: http://127.0.0.1:8000"
echo "Disable: systemctl --user disable --now terminal-ai.service"
if command -v loginctl >/dev/null 2>&1; then
  if loginctl enable-linger "$USER" 2>/dev/null; then
    echo "User lingering enabled: service can start at boot before interactive login."
  else
    echo "Could not enable lingering automatically. If boot-before-login startup is needed, run: loginctl enable-linger $USER" >&2
  fi
else
  echo "loginctl unavailable; service starts when the user manager starts (usually at login)." >&2
fi
