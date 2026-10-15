$ErrorActionPreference = "Stop"
$AppDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $AppDir ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Run .\install.ps1 first." }
$TaskName = "TerminalAI-Web"
$Action = New-ScheduledTaskAction -Execute $Python -Argument "-m uvicorn app:app --host 127.0.0.1 --port 8000" -WorkingDirectory $AppDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "Start Terminal AI locally at sign-in." -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Startup task installed and started. Dashboard: http://127.0.0.1:8000"
Write-Host "Manage/remove task in Task Scheduler under TerminalAI-Web."
