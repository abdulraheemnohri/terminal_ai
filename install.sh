#!/usr/bin/env sh
# terminal-ai setup helper for Linux/macOS/WSL.
set -eu

PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || {
  echo "Python 3 was not found. Install Python 3.10+ and retry." >&2
  exit 1
}

"$PYTHON" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install google-genai litert-lm huggingface_hub

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Edit it to configure API keys."
fi

.venv/bin/python -m py_compile terminal_ai.py
echo "Setup complete. Run: .venv/bin/python terminal_ai.py"
echo "Optional health check: .venv/bin/python terminal_ai.py --diagnose"
