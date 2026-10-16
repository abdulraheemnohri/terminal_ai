$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment missing. Run install.ps1 first." }
Set-Location $Repo

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
& $Python -m uvicorn app:app --host $HostAddress --port $Port
exit $LASTEXITCODE
