#!/data/data/com.termux/files/usr/bin/sh
# Optional Termux:Boot entry point. Copy this file into ~/.termux/boot/ after installing Termux:Boot.
set -eu
ROOT="${TERMINAL_AI_ROOT:-$HOME/terminal_ai}"
if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "Terminal AI virtualenv not found at $ROOT/.venv" >> "$HOME/terminal-ai-boot.log"
  exit 1
fi
mkdir -p "$HOME"
cd "$ROOT"
# Prevent duplicate servers on repeated boot broadcasts.
if command -v pgrep >/dev/null 2>&1 && pgrep -f "$ROOT/.venv/bin/python -m uvicorn app:app" >/dev/null 2>&1; then
  exit 0
fi
nohup "$ROOT/.venv/bin/python" -m uvicorn app:app --host "${TERMINAL_AI_HOST:-127.0.0.1}" --port "${TERMINAL_AI_PORT:-8000}" >> "$HOME/terminal-ai-server.log" 2>&1 &
