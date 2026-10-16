#!/usr/bin/env sh
# Backwards-compatible wrapper; implementation lives in scripts/start-server.sh.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec sh "$ROOT/scripts/start-server.sh" "$@"
