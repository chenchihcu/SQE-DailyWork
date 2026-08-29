param(
    [string]$DbPath,
    [string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    throw "Missing venv python: $pythonExe"
}

if ([string]::IsNullOrWhiteSpace($DbPath)) {
    $DbPath = Join-Path $repoRoot "data\sqe_v2.db"
}
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $repoRoot "scratch\formal-db-promotion-status.json"
}

$scriptPath = Join-Path $repoRoot "scripts\audit_formal_db_promotion_status.py"
& $pythonExe $scriptPath --db $DbPath --output $OutputPath
if ($LASTEXITCODE -ne 0) {
    throw "Formal DB promotion status audit reported not ready (exit $LASTEXITCODE)."
}

Write-Host "Formal DB promotion status audit passed: $OutputPath"
