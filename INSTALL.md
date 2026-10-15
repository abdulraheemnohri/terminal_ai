# Terminal AI — Installation and Troubleshooting

This guide installs the local-first Litestar web app. The dashboard is the supported interface; `terminal_ai.py` is its internal agent engine.

## 1. Requirements

- Python 3.10 or newer.
- Git.
- A browser.
- Internet access to install packages.
- A cloud provider API key **or** a compatible local LiteRT-LM model/runtime.

Python 3.12 is used in CI. LiteRT-LM package and model support depends on the platform and architecture; local inference is optional and may not install on every system.

## 2. Linux, macOS, or WSL

```bash
git clone https://github.com/abdulraheemnohri/terminal_ai.git
cd terminal_ai
sh install.sh
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Keep the terminal open and stop the server with Ctrl+C.

For development with automatic reload:

```bash
.venv/bin/litestar --app app:app run --reload --host 127.0.0.1 --port 8000
```

## 3. Windows 10/11 — PowerShell

Install Python 3.10+ and Git, then run:

```powershell
git clone https://github.com/abdulraheemnohri/terminal_ai.git
Set-Location terminal_ai
.\install.ps1
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

If script execution policy prevents running the installer, you can run the same commands manually in PowerShell, or use `powershell -ExecutionPolicy Bypass -File .\install.ps1` if permitted by your device policy. Do not change system policy globally just for this project.

Development server:

```powershell
.\.venv\Scripts\litestar.exe --app app:app run --reload --host 127.0.0.1 --port 8000
```

If the Litestar executable is unavailable, use the Uvicorn command above.

## 4. Termux (Android terminal)

```bash
pkg update
pkg install python git
git clone https://github.com/abdulraheemnohri/terminal_ai.git
cd terminal_ai
sh install.sh
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open the address in a browser on the same device. Some Python wheels, especially LiteRT-LM runtime packages, may not support Termux/Android or your device architecture. If installation fails on a platform-specific runtime dependency, use a supported Linux/Windows environment or troubleshoot that dependency separately. Do not assume cloud inference requires LiteRT-LM to work.

## 5. Configure an AI provider

The installer copies `.env.example` to `.env` only if no `.env` already exists. Open `.env` in a local editor and replace placeholders as needed.

```dotenv
GEMINI_API_KEY=replace_with_your_real_gemini_api_key
HF_TOKEN=replace_with_your_huggingface_token
# TERMINAL_AI_MODE=auto
```

- Gemini: https://aistudio.google.com/app/apikey
- Hugging Face token for gated downloads (optional): https://huggingface.co/settings/tokens

Other cloud providers can be configured in **Settings → Cloud AI provider**. Enter the provider's API key and optionally a model ID. Keys are written to the local `.env` file; do not share this file. Custom remote endpoints require HTTPS; HTTP is accepted only for loopback/local endpoints.

Supported initial modes: `auto`, `cloud`, `local`, `hybrid`. The app will not silently download a large local model at startup. Select and confirm a model download in the Models page.

## 6. Local models and storage

Default locations:

- State/settings: `~/.terminal_ai/`
- Models: `~/terminal-ai/models/`

Override with `TERMINAL_AI_STATE` and `TERMINAL_AI_MODELS`. Local inference requires a compatible `.litertlm` artifact and a supported LiteRT-LM Python API runtime. No CLI subprocess is used for inference.

## 7. Verify the installation

The installer runs Python syntax checks. To run the unit tests manually:

Linux/macOS/WSL/Termux:

```bash
.venv/bin/python -m pytest -q
```

Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

To check the installed dependencies:

```bash
.venv/bin/python -m pip check
```

## 8. Troubleshooting

- **Port 8000 is busy:** use port 8001 in the start command and open http://127.0.0.1:8001.
- **No provider configured:** choose a provider in Settings and configure its key, or install a compatible local model.
- **Provider connection test fails:** check the key, account/model access, network connectivity, and model ID. Do not paste secrets into bug reports.
- **LiteRT-LM fails to install:** confirm support for your OS, Python version, and CPU architecture. The cloud backends are separate from the local LiteRT-LM runtime.
- **Dashboard doesn't load:** check the terminal traceback and verify you started from the repository root with the virtual environment activated.
- **Settings don't take effect:** restart the app after changing process-level environment variables.
- **Keep it private:** default to localhost. Do not bind to `0.0.0.0` on an untrusted network without authentication and other protections.


## 9. New memory, workspace, and scheduling features

After updating to a release containing these features, open the dashboard and use **Knowledge Base**, **Workspace Tools**, and **Task Scheduler** in the sidebar.

- **Knowledge Base:** local SQLite knowledge is stored under the application state directory in `long_term_memory.sqlite3`. It works without internet or an embedding model. Search is lexical, not semantic vector search.
- **Conversation archive:** successful chat turns can be archived locally and searched from Knowledge Base. Turn archiving can be disabled in Settings. Existing records are not deleted when disabled.
- **Workspace Tools:** browsing and reading are confined to the repository root. Writes and commands require a separate approval checkbox and confirmation. Commands run as the same OS user as the app; this is not a container-grade security sandbox. Do not expose this UI to untrusted networks.
- **Task Scheduler:** tasks persist under the application state directory and run while the server is running. Available types are diagnostics, memory backup, and temporary-file cleanup. There is no arbitrary scheduled shell execution. Use Settings to pause background jobs.
- **Data backup:** memory backups are stored in the state directory's `backups` folder. Include the state directory in your own backup plan if you want to preserve all settings, memory, sessions, and schedules.


## 6. Start automatically at user login

Autostart is optional and deliberately uses the current user account, with the dashboard bound to localhost by default.

### Linux with systemd

After installation, run:

```bash
sh install-service.sh
systemctl --user status terminal-ai.service
```

This creates a user service with automatic restart after a process failure. Disable/remove it with `sh uninstall-service.sh`. For startup before login, optionally enable lingering with `loginctl enable-linger "$USER"`.

### Windows 10/11

In PowerShell from the project directory, run:

```powershell
.\\install-startup.ps1
```

This registers a Scheduled Task for the current user's logon. Remove it with `./uninstall-startup.ps1`.

### Manual start

Use `sh start-server.sh` on Linux/macOS/WSL or `./start-server.ps1` in PowerShell. Open http://127.0.0.1:8000.

## 7. Safely update Terminal AI

- Linux/macOS/WSL: `sh update.sh`
- Windows PowerShell: `./update.ps1`

The helper stops if the Git working tree has local changes, uses fast-forward-only updates, installs the project's Python requirements, checks dependency consistency and Python syntax, runs tests, and restarts the configured service/task when detected. Review backups before updating. It updates the **project**, not the operating system; use the OS's normal trusted security-update mechanism for system packages. Automatic project updates are off by default. On Linux/systemd, opt in with `sh install-auto-update.sh`; disable with `sh uninstall-auto-update.sh`. The weekly timer runs the guarded updater, which fast-forwards `origin/main`, installs dependencies, runs checks/tests and restarts the user service if configured. This updates Terminal AI only, not operating-system packages. Windows and macOS updates are manual. Review the Git remote and rollback policy before enabling unattended source updates.

### macOS

Run `sh install-launchagent.sh` to register a per-user LaunchAgent that starts at login and restarts the server if it exits. Remove it with `sh uninstall-launchagent.sh`. Logs are stored under `~/Library/Logs/`.


### Optional weekly automatic project updates

Automatic updates are opt-in. The scripts update Terminal AI source/dependencies only, never operating-system packages. Keep backups and review the Git remote before enabling unattended code updates.

- **Linux/systemd:** run `sh install-auto-update.sh`; inspect with `systemctl --user list-timers terminal-ai-update.timer` and `journalctl --user -u terminal-ai-update.service`; remove with `sh uninstall-auto-update.sh`.
- **macOS:** run `sh install-auto-update-macos.sh`; logs are in `~/Library/Logs/terminal-ai-update.log` and `terminal-ai-update-error.log`; remove with `sh uninstall-auto-update-macos.sh`.
- **Windows:** run `./install-auto-update.ps1` in PowerShell; remove with `./uninstall-auto-update.ps1`. The current user must be signed in.
- **Termux:** automatic updates are not enabled by the boot helper. Run `sh update.sh` manually after reviewing local changes.

Linux's user timer may require systemd lingering to run before login. The macOS LaunchAgent and Windows task run in the logged-in user's context. If validation fails, inspect logs and recover manually rather than bypassing checks.


## 10. Termux automatic start after Android reboot

Termux cannot start itself after a device reboot without the separate **Termux:Boot** add-on. Install Termux:Boot from the same trusted distribution source as Termux, open it once, then from the project directory run:

```sh
mkdir -p ~/.termux/boot
cp termux-boot/com.terminal-ai.start.sh ~/.termux/boot/
chmod 700 ~/.termux/boot/com.terminal-ai.start.sh
```

Edit the copied script's `PROJECT_DIR` if the repository is not at `$HOME/terminal_ai`. The script starts Uvicorn bound to `127.0.0.1:8000` and writes logs to `~/.terminal_ai/logs/termux-server.log`. Open Termux after a reboot if Android battery/background restrictions delay startup. Check the log if the server did not start. No OS update or unattended source update is performed by this boot helper.


## 8. Automatic server startup

First finish the normal install, then explicitly install the service for your platform:

- **Linux:** `sh scripts/install-service.sh`. Check `systemctl --user status terminal-ai.service`; logs: `journalctl --user -u terminal-ai.service -f`. By default it starts at login. For boot-before-login, set `TERMINAL_AI_ENABLE_LINGER=1` when running the installer; this may require system administrator approval.
- **macOS:** `sh scripts/install-service.sh`. The LaunchAgent starts at login. See `~/Library/Logs/terminal-ai.log`.
- **Windows PowerShell:** `.\\scripts\\install-service.ps1`. Inspect with `Get-ScheduledTask -TaskName 'Terminal AI Web Server'`.
- **Termux:** follow the Termux:Boot steps in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Android may still stop background services.

All service installers default to localhost. They do not configure public network access or authentication for you.

## 9. Updating safely

The dashboard's update checker is advisory. On Linux/macOS, run `sh scripts/update.sh` during a maintenance window. It refuses uncommitted changes and non-fast-forward updates, saves a Git bundle, installs dependencies, compiles modules, runs tests, and restarts a detected service. It does not silently apply updates in the background. For Windows, review/pull the update, run tests, then restart the scheduled task manually.

For full service management, logs, security checklist, and platform limitations, see [Production deployment](docs/DEPLOYMENT.md).
