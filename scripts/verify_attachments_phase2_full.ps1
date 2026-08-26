param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phase2FullVerify = Join-Path $PSScriptRoot "verify.ps1"
if (-not (Test-Path -LiteralPath $phase2FullVerify -PathType Leaf)) {
    throw "Full verify runner not found: $phase2FullVerify"
}

& $phase2FullVerify -Profile Full
exit $LASTEXITCODE
