$ErrorActionPreference = "Stop"
$AppDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $AppDir
$Python = Join-Path $AppDir ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Run .\install.ps1 first." }
$Status = git status --porcelain
if ($LASTEXITCODE -ne 0) { throw "Git status failed." }
if ($Status) { throw "Refusing update: working tree has local changes. Commit/stash them first." }
$StateDir = if ($env:TERMINAL_AI_STATE) { $env:TERMINAL_AI_STATE } else { Join-Path $HOME ".terminal_ai" }
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Backup = Join-Path $StateDir "pre-update-$Stamp.zip"
$Items = @(Get-ChildItem -Force $StateDir)
if ($Items.Count -gt 0) { Compress-Archive -Path (Join-Path $StateDir "*") -DestinationPath $Backup -Force }
git fetch origin main
if ($LASTEXITCODE -ne 0) { throw "git fetch failed." }
git merge --ff-only origin/main
if ($LASTEXITCODE -ne 0) { throw "Fast-forward update failed." }
& $Python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
& $Python -m pip check
if ($LASTEXITCODE -ne 0) { throw "Dependency check failed." }
& $Python -m py_compile app.py terminal_ai.py litert_api_backend.py api_provider_backend.py
if ($LASTEXITCODE -ne 0) { throw "Python syntax check failed." }
$Task = Get-ScheduledTask -TaskName "TerminalAI-Web" -ErrorAction SilentlyContinue
if ($Task) { Stop-ScheduledTask -TaskName "TerminalAI-Web" -ErrorAction SilentlyContinue; Start-ScheduledTask -TaskName "TerminalAI-Web" } else { Write-Host "Update installed. Restart manually launched server." }
Write-Host "Update complete. State backup: $Backup"
