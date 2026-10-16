#!/usr/bin/env sh
# Install a per-user macOS LaunchAgent. Run after sh install.sh.
set -eu
if [ "$(uname -s)" != "Darwin" ]; then
  echo "This installer is for macOS only." >&2
  exit 1
fi
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON="$ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "Virtual environment not found. Run sh install.sh first." >&2
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
      echo "Refusing non-loopback bind ($HOST). Configure and review network security before explicitly setting TERMINAL_AI_ALLOW_REMOTE=1." >&2
      exit 2
    fi
    echo "WARNING: non-loopback binding enabled; Terminal AI is not a hardened multi-tenant service." >&2
    ;;
esac

PLIST_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/Library/Logs"
PLIST="$PLIST_DIR/com.terminal-ai.server.plist"
mkdir -p "$PLIST_DIR" "$LOG_DIR"
"$PYTHON" - "$ROOT" "$PYTHON" "$HOST" "$PORT" "$PLIST" "$LOG_DIR" <<'PY'
import plistlib
import sys
from pathlib import Path

root, python, host, port, plist_path, log_dir = sys.argv[1:]
payload = {
    "Label": "com.terminal-ai.server",
    "ProgramArguments": [python, "-m", "uvicorn", "app:app", "--host", host, "--port", port],
    "WorkingDirectory": root,
    "RunAtLoad": True,
    "KeepAlive": True,
    "ProcessType": "Background",
    "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
    "StandardOutPath": str(Path(log_dir) / "terminal-ai.log"),
    "StandardErrorPath": str(Path(log_dir) / "terminal-ai-error.log"),
}
with open(plist_path, "wb") as stream:
    plistlib.dump(payload, stream, sort_keys=True)
PY
DOMAIN="gui/$(id -u)"
launchctl bootout "$DOMAIN" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl kickstart -k "$DOMAIN/com.terminal-ai.server"
echo "LaunchAgent installed and started."
echo "Dashboard: http://127.0.0.1:$PORT (if the host is loopback)"
echo "Status: launchctl print $DOMAIN/com.terminal-ai.server"
echo "Logs: $LOG_DIR/terminal-ai.log and $LOG_DIR/terminal-ai-error.log"
echo "Uninstall: sh scripts/uninstall-launchagent.sh"
