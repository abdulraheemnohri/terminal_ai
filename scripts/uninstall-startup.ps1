# Compatibility forwarding entrypoint. Canonical legacy implementation remains at repository root.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Target = Join-Path $Root "uninstall-startup.ps1"
if (-not (Test-Path -LiteralPath $Target)) { throw "Missing script: $Target" }
& $Target @args
exit $LASTEXITCODE
