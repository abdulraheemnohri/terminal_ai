$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path ".git")) { throw "This directory is not a Git checkout." }
$Changes = git status --porcelain
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect Git status." }
if ($Changes) { throw "Working tree has changes. Commit/stash them before updating; no files changed." }
$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Run .\install.ps1 first." }
git fetch origin
if ($LASTEXITCODE -ne 0) { throw "git fetch failed." }
git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { throw "Fast-forward update failed. No automatic merge was attempted." }
& $Python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
& $Python -m pip check
if ($LASTEXITCODE -ne 0) { throw "Dependency consistency check failed." }
& $Python -m py_compile app.py terminal_ai.py
if ($LASTEXITCODE -ne 0) { throw "Syntax validation failed." }
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed. Review output before restarting the server." }
$Task = Get-ScheduledTask -TaskName "TerminalAI" -ErrorAction SilentlyContinue
if ($Task) {
  Stop-ScheduledTask -TaskName "TerminalAI" -ErrorAction SilentlyContinue
  Start-ScheduledTask -TaskName "TerminalAI"
  Write-Host "Updated and restarted the TerminalAI logon task."
} else {
  Write-Host "Update checks passed. Restart the running server to load the new code."
}
