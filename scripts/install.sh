#!/usr/bin/env sh
# Install Terminal AI for Linux, macOS, WSL, and Termux.
set -eu

# Always operate from the directory containing this script.
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$SCRIPT_DIR"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Python 3 was not found. Install Python 3.10+ and retry." >&2
  echo "Termux: pkg install python git" >&2
  exit 1
fi

"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || {
  echo "Python 3.10 or newer is required. Detected:" >&2
  "$PYTHON" --version >&2
  exit 1
}

if [ ! -d .venv ]; then
  "$PYTHON" -m venv .venv
fi

VENV_PYTHON=".venv/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
  echo "The virtual environment Python was not created at $VENV_PYTHON." >&2
  echo "If this is Termux, ensure Python and venv support are installed." >&2
  exit 1
fi

"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r requirements.txt
"$VENV_PYTHON" -m pip check

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Edit it locally to configure an AI provider."
elif [ -f .env ]; then
  echo "Keeping existing .env."
fi

"$VENV_PYTHON" -m py_compile app.py terminal_ai.py litert_api_backend.py api_provider_backend.py terminal_ai_runtime.py

echo ""
echo "Installation and syntax checks completed."
echo "Start the web UI with:"
echo "  .venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000"
echo "Then open http://127.0.0.1:8000"
echo "Run tests with: .venv/bin/python -m pytest -q"
