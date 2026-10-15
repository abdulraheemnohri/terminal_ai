#!/data/data/com.termux/files/usr/bin/sh
# Copy this file to ~/.termux/boot/ and edit PROJECT_DIR if needed.
# Requires the separate Termux:Boot Android add-on.
set -eu
PROJECT_DIR="${TERMINAL_AI_PROJECT_DIR:-$HOME/terminal_ai}"
PYTHON="$PROJECT_DIR/.venv/bin/python"
STATE_DIR="${TERMINAL_AI_STATE:-$HOME/.terminal_ai}"
LOG_DIR="$STATE_DIR/logs"
LOG_FILE="$LOG_DIR/termux-server.log"
PID_FILE="$STATE_DIR/termux-server.pid"
mkdir -p "$LOG_DIR" "$STATE_DIR"

if [ ! -x "$PYTHON" ]; then
  printf 'Terminal AI boot start skipped: Python not found at %s\n' "$PYTHON" >> "$LOG_FILE"
  exit 1
fi
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE" 2>/dev/null || true)
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    exit 0
  fi
  rm -f "$PID_FILE"
fi

# Keep the dashboard loopback-only; do not expose the phone to the LAN.
cd "$PROJECT_DIR"
nohup "$PYTHON" -m uvicorn app:app --host 127.0.0.1 --port 8000 >> "$LOG_FILE" 2>&1 &
SERVER_PID=$!
printf '%s\n' "$SERVER_PID" > "$PID_FILE"
