#!/usr/bin/env sh
# Install a per-user systemd service. Boot-before-login persistence is opt-in.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON="$ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "Virtual environment not found. Run sh install.sh first." >&2
  exit 1
fi
if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemd is not available. Use start-server.sh or your OS service manager." >&2
  exit 1
fi

HOST="${TERMINAL_AI_HOST:-127.0.0.1}"
PORT="${TERMINAL_AI_PORT:-8000}"
case "$HOST" in
  *[!A-Za-z0-9.:_-]*|'') echo "TERMINAL_AI_HOST contains unsupported characters." >&2; exit 2 ;;
esac
case "$PORT" in
  ''|*[!0-9]*) echo "TERMINAL_AI_PORT must be an integer from 1 to 65535." >&2; exit 2 ;;
esac
if [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
  echo "TERMINAL_AI_PORT must be an integer from 1 to 65535." >&2
  exit 2
fi
case "$HOST" in
  127.0.0.1|localhost|::1) ;;
  *)
    if [ "${TERMINAL_AI_ALLOW_REMOTE:-0}" != "1" ]; then
      echo "Refusing non-loopback bind ($HOST). Set TERMINAL_AI_ALLOW_REMOTE=1 only after configuring authentication, TLS, CSRF/origin checks, rate limits, and firewall rules." >&2
      exit 2
    fi
    echo "WARNING: non-loopback binding enabled; Terminal AI is not a hardened multi-tenant service." >&2
    ;;
esac

SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"
cat > "$SERVICE_DIR/terminal-ai.service" <<EOF
[Unit]
Description=Terminal AI local web agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory="$ROOT"
Environment=PYTHONUNBUFFERED=1
ExecStart="$PYTHON" -m uvicorn app:app --host $HOST --port $PORT
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
echo "Dashboard: http://127.0.0.1:$PORT (if the host is loopback)"
echo "Disable: systemctl --user disable --now terminal-ai.service"

if [ "${TERMINAL_AI_ENABLE_LINGER:-0}" = "1" ]; then
  if command -v loginctl >/dev/null 2>&1; then
    loginctl enable-linger "$USER"
    echo "User lingering enabled: service can start at boot before interactive login."
  else
    echo "Cannot enable boot-before-login: loginctl is unavailable." >&2
    exit 1
  fi
else
  echo "Boot-before-login persistence was not enabled."
  echo "Opt in only if needed: TERMINAL_AI_ENABLE_LINGER=1 sh scripts/install-service.sh"
fi
