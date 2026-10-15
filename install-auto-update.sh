#!/usr/bin/env sh
# Opt-in weekly automatic Terminal AI project updates via a systemd user timer.
# This updates project source/dependencies, not the host operating system.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
[ -x "$ROOT/.venv/bin/python" ] || { echo "Run sh install.sh first." >&2; exit 1; }
command -v systemctl >/dev/null 2>&1 || { echo "systemd is required." >&2; exit 1; }
systemctl --user show-environment >/dev/null 2>&1 || { echo "systemd user manager unavailable. Start a user session or enable lingering if appropriate." >&2; exit 1; }
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"
cat > "$UNIT_DIR/terminal-ai-update.service" <<EOF
[Unit]
Description=Safely update Terminal AI from origin/main

[Service]
Type=oneshot
WorkingDirectory=$ROOT
ExecStart=$ROOT/update.sh
EOF
cat > "$UNIT_DIR/terminal-ai-update.timer" <<'EOF'
[Unit]
Description=Weekly Terminal AI update check

[Timer]
OnCalendar=Sun *-*-* 04:30:00
Persistent=true
RandomizedDelaySec=30m
Unit=terminal-ai-update.service

[Install]
WantedBy=timers.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now terminal-ai-update.timer
echo "Weekly project updates enabled (Sunday 04:30, local system time, randomized delay)."
echo "Timer: systemctl --user list-timers terminal-ai-update.timer"
echo "Logs: journalctl --user -u terminal-ai-update.service"
echo "Disable: sh uninstall-auto-update.sh"
echo "Updates pull and execute code from origin/main. Review your remote and backup policy first."
