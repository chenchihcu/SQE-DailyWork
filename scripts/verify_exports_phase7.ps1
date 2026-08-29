param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phase7RepoRoot = Split-Path -Parent $PSScriptRoot
$phase7Python = Join-Path $phase7RepoRoot ".venv\Scripts\python.exe"
$phase7Ruff = Join-Path $phase7RepoRoot ".venv\Scripts\ruff.exe"
$phase7FormalDb = Join-Path $phase7RepoRoot "data\sqe_v2.db"
$phase7FingerprintScript = Join-Path $phase7RepoRoot "scripts\sqlite_readonly_fingerprint.py"
$phase7ScratchRoot = Join-Path $phase7RepoRoot "scratch\phase7-focused"
$phase7VerificationDir = Join-Path $phase7ScratchRoot ([Guid]::NewGuid().ToString("N"))
$phase7VerificationDb = Join-Path $phase7VerificationDir "sqe_v2.db"

if (-not (Test-Path -LiteralPath $phase7Python -PathType Leaf)) {
    throw "Phase 7 Python runtime not found: $phase7Python"
}
if (-not (Test-Path -LiteralPath $phase7Ruff -PathType Leaf)) {
    throw "Phase 7 Ruff runtime not found: $phase7Ruff"
}
if (-not (Test-Path -LiteralPath $phase7FormalDb -PathType Leaf)) {
    throw "Formal source database not found: $phase7FormalDb"
}

$phase7FormalFingerprintBefore = & $phase7Python $phase7FingerprintScript `
    --digest-only $phase7FormalDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to fingerprint the formal database before Phase 7 focused verification."
}
New-Item -ItemType Directory -Path $phase7VerificationDir -Force | Out-Null
& $phase7Python (Join-Path $PSScriptRoot "sqlite_backup.py") `
    $phase7FormalDb $phase7VerificationDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to create the Phase 7 focused disposable database."
}

$phase7PreviousPythonPath = $env:PYTHONPATH
$phase7PreviousDbPath = $env:SQE_DB_PATH
$phase7PreviousDisposableGuard = $env:SQE_REQUIRE_DISPOSABLE_DB
try {
    Push-Location -LiteralPath $phase7RepoRoot
    $env:PYTHONPATH = "$phase7RepoRoot\src;$phase7RepoRoot"
    $env:SQE_DB_PATH = $phase7VerificationDb
    $env:SQE_REQUIRE_DISPOSABLE_DB = "1"
    $env:QT_QPA_PLATFORM = "offscreen"

    Write-Host "[preflight] initialize disposable export-phase7 database"
    & $phase7Python -c @"
from database.connection import initialize_database
initialize_database()
print('exports phase7 disposable ready')
"@
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 7 disposable preflight failed with exit code $LASTEXITCODE."
    }

    & $phase7Ruff check `
        src/database/anomaly_repeat_repository.py `
        src/services/event/_hypothesis_tree_png.py `
        src/services/event/_anomaly_markdown.py `
        src/services/manager_export_service.py `
        src/services/supplier_report_service.py `
        scripts/generate_weekly_report.py `
        tests/test_exports_phase7.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 7 focused Ruff gate failed with exit code $LASTEXITCODE."
    }

    & $phase7Python -m pytest -q `
        tests/test_exports_phase7.py `
        tests/test_supplier_report_export.py `
        tests/test_excel_report_custom_range.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 7 focused tests failed with exit code $LASTEXITCODE."
    }
    Write-Host "Phase 7 focused checks passed on disposable database: $phase7VerificationDb"
}
finally {
    Pop-Location
    if ([string]::IsNullOrWhiteSpace($phase7PreviousPythonPath)) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $phase7PreviousPythonPath
    }
    if ([string]::IsNullOrWhiteSpace($phase7PreviousDbPath)) {
        Remove-Item Env:SQE_DB_PATH -ErrorAction SilentlyContinue
    } else {
        $env:SQE_DB_PATH = $phase7PreviousDbPath
    }
    if ([string]::IsNullOrWhiteSpace($phase7PreviousDisposableGuard)) {
        Remove-Item Env:SQE_REQUIRE_DISPOSABLE_DB -ErrorAction SilentlyContinue
    } else {
        $env:SQE_REQUIRE_DISPOSABLE_DB = $phase7PreviousDisposableGuard
    }
}

$phase7FormalFingerprintAfter = & $phase7Python $phase7FingerprintScript `
    --digest-only $phase7FormalDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to fingerprint the formal database after Phase 7 focused verification."
}
if ($phase7FormalFingerprintBefore -ne $phase7FormalFingerprintAfter) {
    throw "Formal database fingerprint changed during Phase 7 focused verification."
}
Write-Host "Formal database fingerprint unchanged: $phase7FormalFingerprintBefore"
