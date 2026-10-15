# Install Terminal AI for Windows PowerShell.
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$PyLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $PyLauncher) {
    throw "Python launcher 'py' was not found. Install Python 3.10+ and retry."
}

& py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.10 or newer is required. Install a supported Python version and retry."
}

if (-not (Test-Path ".venv")) {
    & py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the .venv virtual environment." }
}

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment Python was not found at $Python."
}

& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip." }

& $Python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed. Review the pip error above." }

& $Python -m pip check
if ($LASTEXITCODE -ne 0) { throw "Dependency consistency check failed." }

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Edit it locally to configure an AI provider."
} elseif (Test-Path ".env") {
    Write-Host "Keeping existing .env."
}

& $Python -m py_compile app.py terminal_ai.py litert_api_backend.py api_provider_backend.py terminal_ai_runtime.py
if ($LASTEXITCODE -ne 0) { throw "Python syntax check failed." }

Write-Host ""
Write-Host "Installation and syntax checks completed."
Write-Host "Start the web UI with:"
Write-Host "  .\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000"
Write-Host "Then open http://127.0.0.1:8000"
Write-Host "Run tests with: .\.venv\Scripts\python.exe -m pytest -q"
