# Automatic startup, restart, and updates

Terminal AI can start automatically after Linux/WSL login or boot, Windows sign-in, or Android boot under Termux. The server binds to 127.0.0.1 by default so it is not exposed to your LAN unless you explicitly configure it otherwise.

## Linux / Debian / Ubuntu / WSL with systemd

Run from the project checkout after installation:

```sh
./scripts/install_autostart.sh
systemctl --user status terminal-ai.service
journalctl --user -u terminal-ai.service -f
```

The service starts now and at future logins, and restarts after crashes. On a systemd Linux host, the installer attempts to enable lingering so it can start without an interactive login. If that fails and you want boot-before-login startup, run `sudo loginctl enable-linger "$USER"` yourself.

Remove only the startup entry:

```sh
./scripts/uninstall_autostart.sh
```

## Windows 10/11 PowerShell

After install.ps1, run PowerShell from the project directory:

```powershell
.\install_autostart.ps1
Get-ScheduledTask -TaskName "Terminal AI Web Server"
```

This creates a per-user logon task and starts it immediately. Remove it with:

```powershell
Unregister-ScheduledTask -TaskName "Terminal AI Web Server" -Confirm:$false
```

## Android / Termux

1. Install the Termux:Boot app from the same trusted source as Termux.
2. Open Termux:Boot once so Android registers it.
3. In the project directory run `./scripts/install_autostart.sh`.
4. If the device aggressively stops background processes, review Android battery optimization for Termux.

The boot script writes logs to `$HOME/.terminal_ai/logs/server.log` and requests a Termux wake lock when available. Android vendor power management can still restrict background processes.

## Restart and updates

- Linux restart: `systemctl --user restart terminal-ai.service`.
- Linux logs: `journalctl --user -u terminal-ai.service -f`.
- Windows: use Task Scheduler to stop/start the task.
- Application update checks use the existing Settings → Updates controls and are disabled by default.
- Installing new application code or operating-system packages automatically is not enabled by this installer. Unattended updates can overwrite local changes, change dependencies, or break startup. Check updates, review changes, and back up local state before updating deliberately.

## Security

The default host is 127.0.0.1. Exposing the server to another interface exposes the local agent UI to that network; use authentication and a firewall before doing so. Never run updates with elevated privileges or commit real API keys.
