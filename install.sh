#!/usr/bin/env sh
# Terminal AI Litestar web setup for Linux/macOS/WSL/Termux.
set -eu

PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || {
  echo "Python 3 was not found. Install Python 3.10+ and retry." >&2
  exit 1
}

"$PYTHON" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Edit it locally to configure your API key."
fi

.venv/bin/python -m py_compile app.py terminal_ai.py
echo "Setup complete."
echo "Start web UI: .venv/bin/litestar --app app:app run --host 127.0.0.1 --port 8000"
echo "Then open: http://127.0.0.1:8000"
