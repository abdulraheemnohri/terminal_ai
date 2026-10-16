$ErrorActionPreference = "Stop"
$Root = (Split-Path -Parent $PSScriptRoot)
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found. Run .\install.ps1 first." }
$TaskName = "TerminalAI"
$Action = New-ScheduledTaskAction -Execute $Python -Argument "-m uvicorn app:app --host 127.0.0.1 --port 8000" -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Start Terminal AI local web server at user logon" -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Autostart enabled for the current Windows user."
Write-Host "Dashboard: http://127.0.0.1:8000"
Write-Host 'Disable/remove: Unregister-ScheduledTask -TaskName TerminalAI -Confirm:$false'
