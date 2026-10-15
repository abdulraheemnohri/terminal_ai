# Automatic startup and updates

Automatic startup is opt-in. Keep the web server bound to loopback by default.

## Linux systemd

1. Install and test the project.
2. Review systemd/terminal-ai.service. It expects the checkout at /opt/terminal_ai, a virtualenv at /opt/terminal_ai/.venv, and a dedicated terminal-ai account.
3. Prepare the application files, virtual environment and secret file at those paths. Ensure the service account has only the permissions it needs.
4. Run sudo sh scripts/install_systemd_service.sh and follow the prompts.
5. Check status with sudo systemctl status terminal-ai and logs with sudo journalctl -u terminal-ai -f.
6. Disable startup with sudo systemctl disable --now terminal-ai.

Do not run the agent as root. Review the unit's filesystem restrictions for your chosen state directory instead of weakening them broadly.

## Windows

Run install.ps1, then run powershell -ExecutionPolicy RemoteSigned -File .\scripts\install_autostart_windows.ps1. This registers per-user sign-in startup, not pre-login machine startup. Remove Terminal AI.lnk from the user's Startup folder to disable it. A machine-wide service needs a separately reviewed service wrapper and dedicated account; do not run an agent as LocalSystem merely for autostart.

## macOS and Termux

- macOS: use a reviewed per-user LaunchAgent plist; systemd is not a macOS service manager.
- Termux/Android: Termux:Boot requires the companion add-on and Android background-start permissions. The OS may still stop background processes.

## Automatic updates

Update checks and update installation are separate features. Recommended defaults:
- Check on a configurable schedule and show version, release notes and verification status in the dashboard.
- Do not silently run git pull, install dependencies, change settings or restart the server.
- For an approved update, create a backup, verify a trusted release/commit, stage the update, run tests and health checks, then restart with a rollback path.
- Keep automatic installation disabled until trusted-release verification and rollback are implemented and reviewed.
