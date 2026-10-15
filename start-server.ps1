$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found. Run .\install.ps1 first." }
& $Python -m uvicorn app:app --host 127.0.0.1 --port 8000
exit $LASTEXITCODE
