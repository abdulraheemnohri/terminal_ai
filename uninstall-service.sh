#!/usr/bin/env sh
# Backwards-compatible wrapper; implementation lives in scripts/uninstall-service.sh.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec sh "$ROOT/scripts/uninstall-service.sh" "$@"
