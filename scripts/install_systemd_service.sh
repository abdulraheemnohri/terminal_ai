#!/usr/bin/env sh
set -eu
if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo after reviewing this script and the unit." >&2
  exit 1
fi
ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
UNIT="$ROOT_DIR/systemd/terminal-ai.service"
[ -f "$UNIT" ] || { echo "Missing $UNIT" >&2; exit 1; }
echo "This expects the app at /opt/terminal_ai and service user terminal-ai."
echo "Prepare those paths and review the unit before continuing."
printf "Install the systemd unit? [y/N] "
read answer
[ "$answer" = "y" ] || [ "$answer" = "Y" ] || { echo "Cancelled."; exit 1; }
if ! id terminal-ai >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/terminal-ai --create-home --shell /usr/sbin/nologin terminal-ai
fi
install -d -o terminal-ai -g terminal-ai /var/lib/terminal-ai
install -m 0644 "$UNIT" /etc/systemd/system/terminal-ai.service
systemctl daemon-reload
printf "Enable and start at boot now? [y/N] "
read enable_answer
if [ "$enable_answer" = "y" ] || [ "$enable_answer" = "Y" ]; then
  systemctl enable --now terminal-ai.service
  systemctl --no-pager --full status terminal-ai.service || true
else
  echo "Not enabled. Later: sudo systemctl enable --now terminal-ai"
fi
