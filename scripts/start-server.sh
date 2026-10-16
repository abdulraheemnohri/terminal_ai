#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
PYTHON="$ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then echo "Virtual environment not found. Run: sh install.sh" >&2; exit 1; fi

HOST="${TERMINAL_AI_HOST:-127.0.0.1}"
PORT="${TERMINAL_AI_PORT:-8000}"
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
    echo "WARNING: non-loopback binding enabled. This application is not a hardened multi-tenant service." >&2
    ;;
esac
exec "$PYTHON" -m uvicorn app:app --host "$HOST" --port "$PORT"
