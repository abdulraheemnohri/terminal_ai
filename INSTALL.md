# Installation and Configuration Guide

This guide covers Windows 10/11, Linux, macOS, WSL, and Termux. The project is a Python CLI application; a virtual environment is recommended so dependencies do not affect system Python.

## 1. Requirements

- Python 3.10 or newer (use a currently supported Python release).
- Git (only needed to clone the repository).
- Internet access for installation and Gemini mode. Local mode can run without an API key after the required local runtime and model are available.
- Optional: a Hugging Face token for models that require access approval.

Check versions:

```bash
python --version
git --version
```

On systems where Python 3 is invoked as `python3`, replace `python` with `python3` below.

## 2. Linux / macOS / WSL

Install Git and Python using your distribution's package manager, then:

```bash
git clone https://github.com/abdulraheemnohri/terminal_ai.git
cd terminal_ai
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install google-genai litert-lm huggingface_hub
cp .env.example .env
```

Edit the local `.env` file (for example, with `nano .env`) and replace the fake placeholders with your own credentials. Never commit this file or share it in screenshots/issues.

## 3. Windows 10 / 11 (PowerShell)

Install Python from https://www.python.org/downloads/windows/ (enable the Python PATH option) and Git from https://git-scm.com/download/win. Open a new PowerShell window:

```powershell
git clone https://github.com/abdulraheemnohri/terminal_ai.git
Set-Location terminal_ai
py -3 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
python -m pip install google-genai litert-lm huggingface_hub
Copy-Item .env.example .env
notepad .env
python terminal_ai.py --diagnose
python terminal_ai.py
```

If PowerShell blocks activation, you can skip activation and use the environment's Python directly:

```powershell
.\\.venv\\Scripts\\python.exe -m pip install --upgrade pip
.\\.venv\\Scripts\\python.exe -m pip install google-genai litert-lm huggingface_hub
.\\.venv\\Scripts\\python.exe terminal_ai.py
```

Do not change the machine-wide execution policy just to activate a virtual environment.

## 4. Termux (Android terminal)

Install Termux from a trusted distribution source, then:

```bash
pkg update
pkg install python git
git clone https://github.com/abdulraheemnohri/terminal_ai.git
cd terminal_ai
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install google-genai huggingface_hub
cp .env.example .env
nano .env
```

LiteRT-LM availability depends on the current Termux/Android architecture and package support. If `pip install litert-lm` fails, use cloud mode or consult the LiteRT-LM project's current supported installation instructions; do not assume local inference is installed just because the agent package is installed.

## 5. Configuration

### Set up the local `.env` file

The repository includes a safe `.env.example` template with fake placeholders. Copy it to `.env` and replace those placeholders on your own device; **do not put real credentials in GitHub files**.

```dotenv
GEMINI_API_KEY=replace_with_your_google_gemini_api_key
HF_TOKEN=replace_with_your_huggingface_access_token
```

- Create/manage a Gemini API key in Google AI Studio: https://aistudio.google.com/app/apikey
- Create/manage a Hugging Face token in your account settings: https://huggingface.co/settings/tokens
- Gemini is needed for `cloud`, and may be used by `auto`/`hybrid` modes.
- Hugging Face token is optional unless downloading a gated model or a resource requiring authentication.

Linux/macOS/WSL/Termux: `nano .env` (or another local text editor). Windows: `notepad .env`.

The application checks for a dotenv file in this order: `TERMINAL_AI_ENV`, project `.env`, then `~/.terminal_ai/.env`. Existing operating-system environment variables take precedence over values in the file.

Available variables:

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Gemini API key for cloud, hybrid, and auto modes |
| `HF_TOKEN` | Optional Hugging Face token for gated models |
| `TERMINAL_AI_STATE` | Override the persistent state directory |
| `TERMINAL_AI_MODELS` | Override the local model directory |
| `TERMINAL_AI_DEBUG` | Enable extra diagnostic logging when supported |
| `TERMINAL_AI_ENV` | Use a specific dotenv file |

Never commit real API keys. Do not paste keys into bug reports or screenshots. The repository's `.gitignore` should keep `.env` out of commits; verify with `git status --short` before pushing.

### Model modes

- `auto`: route tasks to the appropriate backend.
- `cloud`: Gemini only; requires `GEMINI_API_KEY`.
- `local`: LiteRT-LM only; requires a compatible local runtime and downloaded model.
- `hybrid`: try cloud and fall back to local when possible.

Example:

```bash
python terminal_ai.py --mode local --diagnose
python terminal_ai.py --auto-download
```

The downloader may need internet access and, for gated models, `HF_TOKEN`.

### Persistent settings

Settings are stored in `~/.terminal_ai/settings.json` by default. From the agent prompt:

```text
/settings
/set mode local
/set temperature 0.5
/set debug on
/set history_limit 20
/set tool_rounds 5
```

Some settings (such as backend mode) take effect after restarting. The interactive `/help` and `/settings` commands show the supported commands and current values for the version installed.

### State and model directories

- State, memory, settings, sessions, and backups: `~/.terminal_ai/`
- Local model files: `~/terminal-ai/models/`

Set `TERMINAL_AI_STATE` or `TERMINAL_AI_MODELS` before launch to use custom locations. Ensure the selected directories are writable and have sufficient free disk space.

## 6. Verify installation and run tests

```bash
python -m py_compile terminal_ai.py
python terminal_ai.py --diagnose
python -m pip install pytest
python -m pytest tests/ -v
```

A successful package installation does not guarantee that a particular LiteRT-LM model is supported on your platform. Use diagnostics to check runtime and model availability.

## 7. Upgrade / uninstall

Upgrade a Git checkout:

```bash
git pull
python -m pip install --upgrade google-genai litert-lm huggingface_hub
python terminal_ai.py --diagnose
```

Before upgrading, back up `~/.terminal_ai/` if the stored memory and sessions matter to you.

To uninstall, deactivate the virtual environment and delete the cloned project directory and its `.venv`. Agent data is stored separately in `~/.terminal_ai/`; remove that directory only if you intentionally want to delete memory, settings, sessions, and backups.
