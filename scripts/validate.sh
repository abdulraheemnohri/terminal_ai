#!/usr/bin/env sh
# Run the repository's local validation suite without changing application state.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
"$PYTHON" scripts/check_structure.py
"$PYTHON" -m compileall -q app.py terminal_ai.py agent application routers
if command -v node >/dev/null 2>&1; then
  node --check web/app.js
  if [ -f web/chat-enhancements.js ]; then node --check web/chat-enhancements.js; fi
else
  echo "WARN: node not installed; JavaScript syntax checks skipped." >&2
fi
for script in scripts/*.sh; do
  [ -f "$script" ] || continue
  sh -n "$script"
done
"$PYTHON" -m pytest -q
