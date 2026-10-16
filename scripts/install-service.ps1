# Install a per-user automatic startup task for Terminal AI on Windows.
# Run after .\install.ps1 from PowerShell.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Missing .venv. Run .\install.ps1 first." }

$HostAddress = if ($env:TERMINAL_AI_HOST) { $env:TERMINAL_AI_HOST } else { "127.0.0.1" }
$Port = if ($env:TERMINAL_AI_PORT) { $env:TERMINAL_AI_PORT } else { "8000" }
if ($Port -notmatch '^\d+$' -or [int]$Port -lt 1 -or [int]$Port -gt 65535) {
  throw "TERMINAL_AI_PORT must be an integer from 1 to 65535."
}
if ($HostAddress -notin @("127.0.0.1", "localhost", "::1")) {
  if ($env:TERMINAL_AI_ALLOW_REMOTE -ne "1") {
    throw "Refusing non-loopback bind ($HostAddress). Set TERMINAL_AI_ALLOW_REMOTE=1 only after configuring authentication, TLS, CSRF/origin checks, rate limits, and firewall rules."
  }
  Write-Warning "Non-loopback binding enabled. Terminal AI is not a hardened multi-tenant service."
}

$TaskName = "Terminal AI Web Server"
$Arguments = "-m uvicorn app:app --host $HostAddress --port $Port"
$Action = New-ScheduledTaskAction -Execute $Python -Argument $Arguments -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Starts the Terminal AI local web server at user logon and restarts it after failure." -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Installed and started '$TaskName'."
Write-Host "Status: Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "Stop:   Stop-ScheduledTask -TaskName '$TaskName'"
Write-Host "Remove: Unregister-ScheduledTask -TaskName '$TaskName'"
Write-Host "Default bind is localhost only. Remote exposure requires a separately reviewed authentication and network-security configuration."
