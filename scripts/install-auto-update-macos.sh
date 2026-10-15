#!/usr/bin/env sh
# Compatibility forwarding entrypoint. Canonical legacy implementation remains at repository root.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TARGET="$ROOT/install-auto-update-macos.sh"
[ -f "$TARGET" ] || { echo "Missing script: $TARGET" >&2; exit 1; }
exec "$TARGET" "$@"
