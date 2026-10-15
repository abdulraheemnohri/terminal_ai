#!/usr/bin/env sh
set -eu
systemctl --user disable --now terminal-ai-update.timer 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/terminal-ai-update.timer" "$HOME/.config/systemd/user/terminal-ai-update.service"
systemctl --user daemon-reload
echo "Automatic Terminal AI project updates disabled. Existing source and state were kept."
