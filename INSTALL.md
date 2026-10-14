# Terminal AI — Litestar Web Installation

Terminal AI now uses a browser dashboard served by Litestar. The old terminal REPL is not the supported interface; `terminal_ai.py` is retained as the internal agent engine imported by `app.py`.

## Requirements

- Python 3.10 or newer
- Git
- A browser
- Gemini API key for cloud inference, or a compatible local LiteRT-LM runtime and model
- Internet access for installing Python packages; local inference can run offline after setup

## Linux / macOS / WSL

```bash
git clone https://github.com/abdulraheemnohri/terminal_ai.git
cd terminal_ai
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your own credentials using a local editor:

```dotenv
GEMINI_API_KEY=replace_with_your_real_gemini_key
HF_TOKEN=replace_with_your_huggingface_token
```

Start the dashboard:

```bash
.venv/bin/litestar --app app:app run --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. API documentation is available at http://127.0.0.1:8000/schema/swagger.

## Windows 10 / 11 (PowerShell)

Install Python and Git, then run:

```powershell
git clone https://github.com/abdulraheemnohri/terminal_ai.git
Set-Location terminal_ai
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
.\.venv\Scripts\litestar.exe --app app:app run --reload --host 127.0.0.1 --port 8000
```

If the Litestar executable is unavailable, use:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

## Termux

```bash
pkg update
pkg install python git
git clone https://github.com/abdulraheemnohri/terminal_ai.git
cd terminal_ai
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
nano .env
uvicorn app:app --host 127.0.0.1 --port 8000
```

Some LiteRT-LM packages may not support all Termux/Android architectures. If local runtime installation is unavailable, use Gemini mode or a supported Linux/Windows environment. Keep the server bound to localhost unless you deliberately configure access controls.

## Configure credentials

- Gemini key: https://aistudio.google.com/app/apikey
- Hugging Face token: https://huggingface.co/settings/tokens

Never commit `.env` or paste real keys into issues. `.env.example` contains placeholders only; verify the current example values before copying. Process environment variables override values loaded from the dotenv file.

## Start and stop

Run the Litestar command in a terminal and leave it running while you use the browser. Stop the server with Ctrl+C. For a stable local session without auto-reload:

```bash
.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
```

## Troubleshooting

- **Backend not ready:** configure `GEMINI_API_KEY`, or install LiteRT-LM and place a compatible `.litertlm` model under the configured models directory.
- **Port busy:** change `--port 8000` to another local port such as `--port 8001`.
- **LiteRT-LM installation fails:** check upstream package support for your operating system and Python version; this does not necessarily indicate a Litestar issue.
- **API docs:** visit `/schema/swagger`.
