#!/usr/bin/env sh
# Backwards-compatible wrapper; implementation lives in scripts/install-launchagent.sh.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec sh "$ROOT/scripts/install-launchagent.sh" "$@"
