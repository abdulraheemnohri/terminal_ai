$ErrorActionPreference = "Stop"
$TaskName = "TerminalAI-AutoUpdate"
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Task) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Weekly automatic project updates disabled."
} else {
    Write-Host "No TerminalAI-AutoUpdate task was registered."
}
