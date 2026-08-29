param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $repoRoot "scripts\verify.ps1") -Profile Full
if ($LASTEXITCODE -ne 0) {
    throw "Phase 4 full verification failed with exit code $LASTEXITCODE."
}
