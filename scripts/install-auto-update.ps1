$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$UpdateScript = Join-Path $Root "update.ps1"
if (-not (Test-Path $UpdateScript)) { throw "update.ps1 was not found in the repository." }
$PowerShell = (Get-Command powershell.exe -ErrorAction Stop).Source
$TaskName = "TerminalAI-AutoUpdate"
$Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $UpdateScript + '"'
$Action = New-ScheduledTaskAction -Execute $PowerShell -Argument $Arguments -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 4:30AM
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10) -ExecutionTimeLimit (New-TimeSpan -Hours 1)
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "Run Terminal AI's guarded project updater weekly." -Force | Out-Null
Write-Host "Weekly Terminal AI project updates scheduled for Sunday at 04:30."
Write-Host "The current user must be signed in for the task to run."
Write-Host "Updates execute code from origin/main; review your remote and backup policy first."
Write-Host "Disable/remove the task named TerminalAI-AutoUpdate in Task Scheduler."
