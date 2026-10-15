$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $PSScriptRoot "start_terminal_ai.ps1"
if (-not (Test-Path (Join-Path $Repo ".venv\Scripts\python.exe"))) { throw "Run install.ps1 first." }
$Startup = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $Startup "Terminal AI.lnk"
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = (Get-Command powershell.exe).Source
$Shortcut.Arguments = "-NoProfile -ExecutionPolicy RemoteSigned -File `"$Launcher`""
$Shortcut.WorkingDirectory = $Repo
$Shortcut.Description = "Start Terminal AI local web server at user sign-in"
$Shortcut.Save()
Write-Host "Registered startup shortcut: $ShortcutPath"
Write-Host "Remove this shortcut to disable automatic startup."
