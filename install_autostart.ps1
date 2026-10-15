# Install Terminal AI as a Windows logon startup task.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { throw "Missing $Python. Run .\install.ps1 first." }
$HostAddress = if ($env:TERMINAL_AI_HOST) { $env:TERMINAL_AI_HOST } else { "127.0.0.1" }
$Port = if ($env:TERMINAL_AI_PORT) { $env:TERMINAL_AI_PORT } else { "8000" }
$TaskName = "Terminal AI Web Server"
$Action = New-ScheduledTaskAction -Execute $Python -Argument "-m uvicorn app:app --host $HostAddress --port $Port" -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Starts the local Terminal AI server at user logon." -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Installed and started '$TaskName'."
Write-Host "Open http://$HostAddress`:$Port"
Write-Host "Remove with: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
