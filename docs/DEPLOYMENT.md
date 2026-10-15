# Production deployment and automatic startup

Terminal AI is a local-first agent, not a hardened multi-tenant service. Production readiness requires environment-specific testing and access controls. The startup helpers default to `127.0.0.1`; do not change the bind address to `0.0.0.0` unless you have configured authentication, TLS/reverse proxy protections, firewall rules, and trusted-network access.

## Linux (systemd user service)

1. Install the project: `sh install.sh`.
2. Run `sh scripts/install-service.sh`.
3. Check with `systemctl --user status terminal-ai.service`.
4. Follow logs with `journalctl --user -u terminal-ai.service -f`.
5. Stop/disable with `systemctl --user disable --now terminal-ai.service`.

This service starts at user login and restarts after process failure. For boot-before-login on a machine you administer, run `TERMINAL_AI_ENABLE_LINGER=1 sh scripts/install-service.sh`; system policy may require administrator approval. Enable lingering only for a user account intended to run persistent services.

## macOS (launchd user agent)

Run `sh scripts/install-service.sh`. It creates `~/Library/LaunchAgents/com.terminal-ai.server.plist`, starts the server, and keeps it alive at user login. Logs are in `~/Library/Logs/terminal-ai.log` and `terminal-ai-error.log`. Unload it with `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.terminal-ai.server.plist`.

## Windows (Task Scheduler)

After `./install.ps1`, run `./scripts/install-service.ps1` in PowerShell. The task starts the server at user logon and retries after failures. Inspect it with `Get-ScheduledTask -TaskName 'Terminal AI Web Server'`; remove it with `Unregister-ScheduledTask -TaskName 'Terminal AI Web Server'`.

## Termux / Android

Android may stop background processes to save battery. Install the separate Termux:Boot app from a trusted source, run `sh install.sh`, then copy `scripts/termux-boot-start.sh` to `~/.termux/boot/terminal-ai` and make it executable. Update `TERMINAL_AI_ROOT` in the script if the repository is not at `~/terminal_ai`. Device battery optimization and vendor restrictions may still prevent persistent startup. The default server binds to localhost.

## Updating safely

The dashboard's update checker is advisory; review updates before applying them. For Linux/macOS, `sh scripts/update.sh` performs a fast-forward-only Git update, creates a source bundle backup, installs dependencies, compiles modules, runs tests, and restarts a managed systemd/launchd service when detected. It refuses dirty worktrees and non-fast-forward changes. It is deliberately not scheduled to apply updates unattended. On Windows, update manually in a reviewed maintenance window, run the tests, then restart the Scheduled Task.

Automatic startup is enabled only after you explicitly install the service. No script silently enables a persistent background process during dependency installation.

## Operational checklist

- Use a dedicated OS account and restrict filesystem permissions.
- Keep secrets in local `.env`; do not commit it or print it to logs.
- Keep the listener on localhost unless network access is secured.
- Back up the state directory and verify the append-only audit hash chain periodically.
- Configure provider/model availability and test startup after OS or Python upgrades.
- Review logs and run `python -m pytest -q` after upgrades.
- Local inference depends on a compatible LiteRT-LM runtime/model and may not be supported on every architecture, including some Android/Termux setups.
