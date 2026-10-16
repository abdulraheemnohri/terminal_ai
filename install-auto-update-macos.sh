#!/usr/bin/env sh
# Backwards-compatible wrapper; implementation lives in scripts/install-auto-update-macos.sh.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec sh "$ROOT/scripts/install-auto-update-macos.sh" "$@"
