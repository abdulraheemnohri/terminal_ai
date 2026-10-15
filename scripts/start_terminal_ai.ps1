$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment missing. Run install.ps1 first." }
Set-Location $Repo
$HostAddress = if ($env:TERMINAL_AI_HOST) { $env:TERMINAL_AI_HOST } else { "127.0.0.1" }
$Port = if ($env:TERMINAL_AI_PORT) { $env:TERMINAL_AI_PORT } else { "8000" }
if ($HostAddress -ne "127.0.0.1" -and $HostAddress -ne "localhost") {
  Write-Warning "Non-local binding requested. Configure authentication, TLS and firewall rules."
}
& $Python -m uvicorn app:app --host $HostAddress --port $Port
exit $LASTEXITCODE
