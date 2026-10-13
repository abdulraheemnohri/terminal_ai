# terminal-ai setup helper for Windows PowerShell.
# Run from the cloned repository directory: .\install.ps1
$ErrorActionPreference = "Stop"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install Python 3 from https://www.python.org/downloads/windows/ and retry."
}

py -3 -m venv .venv
$Python = Join-Path $PWD ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install google-genai litert-lm huggingface_hub

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Edit .env to configure API keys."
}

& $Python -m py_compile terminal_ai.py
Write-Host "Setup complete. Run: .\.venv\Scripts\python.exe terminal_ai.py"
Write-Host "Optional health check: .\.venv\Scripts\python.exe terminal_ai.py --diagnose"
