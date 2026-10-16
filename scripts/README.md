# Terminal AI scripts

Run scripts from a checkout. Python utilities use the current interpreter; use `.venv/bin/python` on Linux/macOS or `.venv\Scripts\python.exe` on Windows when the project virtual environment is installed.

## Maintenance

- `python scripts/doctor.py` — read-only installation/dependency/compilation checks.
- `python scripts/doctor.py --quick` — skip compilation and shell syntax checks.
- `python scripts/backup_state.py` — create a timestamped ZIP backup in `~/terminal-ai-backups`.
- `python scripts/backup_state.py --output-dir /path/to/private/backups` — choose a backup directory.
- `python scripts/restore_state.py /path/to/backup.zip --confirm` — restore only when destination files do not already exist.
- `python scripts/restore_state.py /path/to/backup.zip --confirm --overwrite` — explicitly overwrite existing files; make a backup first.
- `sh scripts/validate.sh` — run structure, compilation, JavaScript syntax, shell syntax, and pytest checks.
- `powershell -ExecutionPolicy Bypass -File scripts/validate.ps1` — equivalent Windows validation.
- `sh scripts/update.sh` — safe fast-forward update with source backup and tests.
- `python scripts/execute_approved_browser_operation.py --operation-id ID --confirm` — execute only an already-approved browser operation from a trusted local terminal.

Backups may contain private conversation state, configuration, and credentials. Store them privately. Restore requires explicit confirmation, verifies checksums and archive paths, and refuses overwrites by default. None of these maintenance utilities grants agent permissions or enables automatic tool execution.

## Platform startup and service scripts

The `scripts/` directory is the canonical home for installer, updater, service, autostart, and maintenance implementations. Root-level commands such as `install.sh`, `update.sh`, and `start-server.sh` are compatibility wrappers that forward into this directory. This avoids duplicated implementations while preserving existing instructions and shortcuts. Review each script before running it, especially scripts that register login/boot services or automatic project updates.

- `scripts/install-service.sh`: per-user Linux systemd service. Boot-before-login persistence is enabled only when `TERMINAL_AI_ENABLE_LINGER=1` is explicitly set during installation.
- `scripts/install_systemd_service.sh`: optional system-wide Linux systemd service; review the expected `/opt/terminal_ai` checkout and dedicated account before use.
- `scripts/install-launchagent.sh` / `scripts/uninstall-launchagent.sh`: per-user macOS LaunchAgent.
- `scripts/install-service.ps1`: Windows Task Scheduler startup.
- `scripts/install_autostart_windows.ps1`: Windows Startup-folder shortcut.
- `scripts/termux-boot-start.sh`: optional Termux:Boot entrypoint.

Server launchers validate the port and refuse non-loopback binding by default. Remote access still requires a separately reviewed security layer; an opt-in bind flag is not authentication.
