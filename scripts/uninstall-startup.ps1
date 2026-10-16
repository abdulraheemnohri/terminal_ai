$ErrorActionPreference = "Stop"
$Task = Get-ScheduledTask -TaskName "TerminalAI" -ErrorAction SilentlyContinue
if ($Task) {
    Stop-ScheduledTask -TaskName "TerminalAI" -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName "TerminalAI" -Confirm:$false
    Write-Host "Terminal AI autostart task removed. Project files and data were kept."
} else {
    Write-Host "No Terminal AI autostart task was registered for this user."
}
