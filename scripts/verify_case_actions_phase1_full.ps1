param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phase1FullVerify = Join-Path $PSScriptRoot "verify.ps1"
if (-not (Test-Path -LiteralPath $phase1FullVerify -PathType Leaf)) {
    throw "Full verify runner not found: $phase1FullVerify"
}

& $phase1FullVerify -Profile Full
exit $LASTEXITCODE
