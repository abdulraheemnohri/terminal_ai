#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
PYTHON="$ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then echo "Virtual environment not found. Run: sh install.sh" >&2; exit 1; fi
exec "$PYTHON" -m uvicorn app:app --host 127.0.0.1 --port 8000
