#!/usr/bin/env sh
# Remove startup entries without deleting project data.
set -eu
if [ -n "${TERMUX_VERSION:-}" ] && [ -d "$HOME/.termux/boot" ]; then rm -f "$HOME/.termux/boot/terminal-ai"; fi
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user disable --now terminal-ai.service >/dev/null 2>&1 || true
  rm -f "$HOME/.config/systemd/user/terminal-ai.service"
  systemctl --user daemon-reload
fi
echo "Removed startup entries if present. Project files and settings were not deleted."
