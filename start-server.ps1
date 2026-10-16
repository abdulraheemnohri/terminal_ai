$ErrorActionPreference = "Stop"
# Backwards-compatible wrapper; implementation lives in scripts/start-server.ps1.
$Target = Join-Path $PSScriptRoot "scripts\start-server.ps1"
if (-not (Test-Path -LiteralPath $Target)) { throw "Missing script: $Target" }
& $Target @args
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
