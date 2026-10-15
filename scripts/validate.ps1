$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root
$Python = if (Test-Path (Join-Path $Root ".venv\Scripts\python.exe")) { Join-Path $Root ".venv\Scripts\python.exe" } else { "python" }
& $Python scripts/check_structure.py
if ($LASTEXITCODE -ne 0) { throw "Structure check failed." }
& $Python -m compileall -q app.py terminal_ai.py agent application routers
if ($LASTEXITCODE -ne 0) { throw "Python compilation failed." }
$Node = Get-Command node -ErrorAction SilentlyContinue
if ($Node) {
    & node --check web/app.js
    if ($LASTEXITCODE -ne 0) { throw "Dashboard JavaScript syntax check failed." }
} else { Write-Warning "Node.js is not installed; JavaScript syntax check skipped." }
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Test suite failed." }
