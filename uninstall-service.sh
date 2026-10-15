#!/usr/bin/env sh
set -eu
if ! command -v systemctl >/dev/null 2>&1; then echo "systemd is not available." >&2; exit 1; fi
systemctl --user disable --now terminal-ai.service 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/terminal-ai.service"
systemctl --user daemon-reload
echo "Terminal AI user service removed. Project files and data were kept."
