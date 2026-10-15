set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
[ "$(id -u)" -ne 0 ] || { echo "Run as normal user." >&2; exit 1; }
command -v systemctl >/dev/null 2>&1 || { echo "systemd required." >&2; exit 1; }
command -v sudo >/dev/null 2>&1 || { echo "sudo required." >&2; exit 1; }
UNIT_DIR=/etc/systemd/system
TMP_SERVICE=$(mktemp); TMP_TIMER=$(mktemp)
trap 'rm -f "$TMP_SERVICE" "$TMP_TIMER"' EXIT HUP INT TERM
cat > "$TMP_SERVICE" <<EOF
[Unit]
Description=Update Terminal AI from configured Git branch
[Service]
Type=oneshot
User=$(id -un)
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/scripts/update.sh
EOF
cat > "$TMP_TIMER" <<'EOF'
[Unit]
Description=Weekly Terminal AI update
[Timer]
OnCalendar=Sun *-*-* 04:30:00
Persistent=true
RandomizedDelaySec=30m
Unit=terminal-ai-auto-update.service
[Install]
WantedBy=timers.target
EOF
sudo install -m 0644 "$TMP_SERVICE" "$UNIT_DIR/terminal-ai-auto-update.service"
sudo install -m 0644 "$TMP_TIMER" "$UNIT_DIR/terminal-ai-auto-update.timer"
sudo systemctl daemon-reload
sudo systemctl enable --now terminal-ai-auto-update.timer
echo "Weekly updates enabled. Disable with sudo systemctl disable --now terminal-ai-auto-update.timer"
