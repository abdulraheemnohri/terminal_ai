# Terminal AI Litestar web setup for Windows PowerShell.
$ErrorActionPreference = "Stop"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install Python 3.10+ and retry."
}

py -3 -m venv .venv
$Python = Join-Path $PWD ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Edit .env locally to configure your API key."
}

& $Python -m py_compile app.py terminal_ai.py
Write-Host "Setup complete."
Write-Host "Start web UI: .\.venv\Scripts\litestar.exe --app app:app run --host 127.0.0.1 --port 8000"
Write-Host "Then open: http://127.0.0.1:8000"
