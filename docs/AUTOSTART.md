# Automatic startup and updates

Automatic startup is opt-in. Keep the web server bound to loopback by default.

## Linux systemd

### Per-user service (recommended)

1. Install the project: `sh install.sh`.
2. Run `sh scripts/install-service.sh` from the checkout. This installs a per-user systemd service and enables it at user login.
3. Check status with `systemctl --user status terminal-ai.service` and logs with `journalctl --user -u terminal-ai.service -f`.
4. Disable startup with `systemctl --user disable --now terminal-ai.service`.

For boot-before-login startup, explicitly opt in by running `TERMINAL_AI_ENABLE_LINGER=1 sh scripts/install-service.sh`. This invokes `loginctl enable-linger`; use it only for an account intended to run persistent services.

### System-wide service (advanced)

The system-wide installer is `sudo sh scripts/install_systemd_service.sh` (underscores). It expects the checkout, virtual environment, and private `.env` to be prepared at `/opt/terminal_ai`, and expects a dedicated `terminal-ai` account. Review `systemd/terminal-ai.service` and the script before running it. Do not run the agent as root. Verify that the service account can read the application and write only to intended state directories.

## Windows

Run `install.ps1`, then run `powershell -ExecutionPolicy RemoteSigned -File .\scripts\install-service.ps1` to register a per-user Task Scheduler task, or use `scripts/install_autostart_windows.ps1` for a Startup-folder shortcut. These start at user logon, not before login. Inspect the task with `Get-ScheduledTask -TaskName 'Terminal AI Web Server'`; remove it with `Unregister-ScheduledTask -TaskName 'Terminal AI Web Server'`. Remove the shortcut from the user's Startup folder to disable that alternative.

The launcher refuses non-loopback binding by default. Do not set `TERMINAL_AI_ALLOW_REMOTE=1` unless authentication, TLS, CSRF/origin protections, rate limiting, and firewall rules have been configured and reviewed.

## macOS and Termux

- macOS: run `sh install-launchagent.sh` (or `sh scripts/install-launchagent.sh`) for a per-user LaunchAgent. Remove it with `sh uninstall-launchagent.sh`.
- Termux/Android: Termux:Boot requires the companion add-on and Android background-start permissions. The OS may still stop background processes.

## Automatic updates

Update checks and update installation are separate features. Update checks may be scheduled, but installation must remain explicit until trusted-release verification and rollback are implemented and reviewed. Do not silently run `git pull`, install dependencies, change settings, or restart the server. For an approved update, create a backup, verify a trusted release/commit, stage the update, run tests and health checks, then restart with a rollback path.

## Disable / recover

- Linux user service: `systemctl --user disable --now terminal-ai.service`
- Linux system service: `sudo systemctl disable --now terminal-ai.service`
- Windows scheduled task: `Unregister-ScheduledTask -TaskName 'Terminal AI Web Server'`
- macOS LaunchAgent: `sh uninstall-launchagent.sh`
- Keep a copy of the previous known-good source and state backup before updates.
