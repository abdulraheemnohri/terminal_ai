$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path (Join-Path $PSScriptRoot ".git"))) {
    throw "This directory is not a Git checkout."
}

$Origin = (git remote get-url origin).Trim().ToLowerInvariant()
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect Git origin." }
$Origin = $Origin -replace '\.git$', ''
if ($Origin -notin @(
    "https://github.com/abdulraheemnohri/terminal_ai",
    "git@github.com:abdulraheemnohri/terminal_ai",
    "ssh://git@github.com/abdulraheemnohri/terminal_ai"
)) {
    throw "Update blocked: origin is not the official Terminal AI repository."
}

$Changes = git status --porcelain
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect Git status." }
if ($Changes) {
    throw "Working tree has changes. Commit/stash them before updating; no project files were changed."
}

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Run .\install.ps1 first." }

$PreviousCommit = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or -not $PreviousCommit) { throw "Unable to determine the current commit." }

$StateDir = if ($env:TERMINAL_AI_STATE) {
    [Environment]::ExpandEnvironmentVariables($env:TERMINAL_AI_STATE)
} else {
    Join-Path $env:USERPROFILE ".terminal_ai"
}
$BackupRoot = Join-Path $StateDir "backups"
$BackupFile = $null
if (Test-Path $StateDir) {
    New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
    $BackupFile = Join-Path $BackupRoot ("pre-update-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".zip")
    $Items = Get-ChildItem -LiteralPath $StateDir -Force | Where-Object { $_.Name -ne "backups" }
    if ($Items) {
        Compress-Archive -Path $Items.FullName -DestinationPath $BackupFile -CompressionLevel Optimal
    } else {
        $BackupFile = $null
    }
}

git fetch origin main
if ($LASTEXITCODE -ne 0) { throw "git fetch failed; the installed project was not changed." }
$RemoteCommit = (git rev-parse origin/main).Trim()
if ($LASTEXITCODE -ne 0 -or -not $RemoteCommit) { throw "Could not resolve origin/main." }
if ($RemoteCommit -eq $PreviousCommit) {
    Write-Host "Terminal AI is already up to date."
    exit 0
}
git merge-base --is-ancestor $PreviousCommit $RemoteCommit
if ($LASTEXITCODE -ne 0) {
    throw "Update blocked: local HEAD is not an ancestor of origin/main. Review local history before updating."
}

$Updated = $false
try {
    git merge --ff-only origin/main
    if ($LASTEXITCODE -ne 0) { throw "Fast-forward update failed. No automatic merge was attempted." }
    $Updated = $true

    & $Python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
    & $Python -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Dependency consistency check failed." }
    & $Python -m compileall -q app.py terminal_ai.py agent api_schemas.py command_control.py memory_store.py selfx_engine.py workspace_tools.py task_scheduler.py routers
    if ($LASTEXITCODE -ne 0) { throw "Python syntax validation failed." }
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Tests failed. The previous source revision will be restored." }
} catch {
    $Failure = $_
    if ($Updated) {
        git reset --hard $PreviousCommit
        if ($LASTEXITCODE -eq 0) {
            & $Python -m pip install -r requirements.txt
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Source rollback succeeded, but restoring the previous dependency set failed. Run pip install -r requirements.txt manually."
            }
            Write-Warning "The previous source revision was restored after update validation failed."
        } else {
            Write-Warning "Automatic source rollback failed. Restore commit $PreviousCommit manually."
        }
    }
    throw $Failure
}

$Task = Get-ScheduledTask -TaskName "TerminalAI" -ErrorAction SilentlyContinue
if ($Task) {
    Stop-ScheduledTask -TaskName "TerminalAI" -ErrorAction SilentlyContinue
    Start-ScheduledTask -TaskName "TerminalAI"
    Write-Host "Updated and restarted the TerminalAI logon task."
} else {
    Write-Host "Update checks passed. Restart the running server to load the new code."
}
if ($BackupFile) { Write-Host "State backup: $BackupFile" }
