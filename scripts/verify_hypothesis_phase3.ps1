param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phase3RepoRoot = Split-Path -Parent $PSScriptRoot
$phase3Python = Join-Path $phase3RepoRoot ".venv\Scripts\python.exe"
$phase3Ruff = Join-Path $phase3RepoRoot ".venv\Scripts\ruff.exe"
$phase3FormalDb = Join-Path $phase3RepoRoot "data\sqe_v2.db"
$phase3FingerprintScript = Join-Path $phase3RepoRoot "scripts\sqlite_readonly_fingerprint.py"
$phase3ScratchRoot = Join-Path $phase3RepoRoot "scratch\phase3-focused"
$phase3VerificationDir = Join-Path $phase3ScratchRoot ([Guid]::NewGuid().ToString("N"))
$phase3VerificationDb = Join-Path $phase3VerificationDir "sqe_v2.db"

if (-not (Test-Path -LiteralPath $phase3Python -PathType Leaf)) {
    throw "Phase 3 Python runtime not found: $phase3Python"
}
if (-not (Test-Path -LiteralPath $phase3Ruff -PathType Leaf)) {
    throw "Phase 3 Ruff runtime not found: $phase3Ruff"
}
if (-not (Test-Path -LiteralPath $phase3FormalDb -PathType Leaf)) {
    throw "Formal source database not found: $phase3FormalDb"
}

$phase3FormalFingerprintBefore = & $phase3Python $phase3FingerprintScript `
    --digest-only $phase3FormalDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to fingerprint the formal database before Phase 3 focused verification."
}
New-Item -ItemType Directory -Path $phase3VerificationDir -Force | Out-Null
& $phase3Python (Join-Path $PSScriptRoot "sqlite_backup.py") `
    $phase3FormalDb $phase3VerificationDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to create the Phase 3 focused disposable database."
}

$phase3PreviousPythonPath = $env:PYTHONPATH
$phase3PreviousDbPath = $env:SQE_DB_PATH
$phase3PreviousDisposableGuard = $env:SQE_REQUIRE_DISPOSABLE_DB
try {
    Push-Location -LiteralPath $phase3RepoRoot
    $env:PYTHONPATH = "$phase3RepoRoot\src;$phase3RepoRoot"
    $env:SQE_DB_PATH = $phase3VerificationDb
    $env:SQE_REQUIRE_DISPOSABLE_DB = "1"

    Write-Host "[preflight] initialize disposable hypothesis contract"
    & $phase3Python -c @"
from database.connection import initialize_database
from database.repository import anomaly_hypotheses_schema_ready
from database import connection as conn_mod
initialize_database()
with conn_mod.get_connection() as conn:
    assert anomaly_hypotheses_schema_ready(conn), 'hypothesis contract not ready'
print('anomaly_hypotheses_v1 ready')
"@
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 3 disposable hypothesis preflight failed with exit code $LASTEXITCODE."
    }

    Write-Host "[preview] hypothesis migration CLI read-only"
    & $phase3Python (Join-Path $PSScriptRoot "migrate_anomaly_hypotheses_v1.py") `
        --db $phase3VerificationDb
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 3 hypothesis migration preview failed with exit code $LASTEXITCODE."
    }

    & $phase3Ruff check `
        src/database/anomaly_hypothesis_repository.py `
        src/database/repository.py `
        src/database/connection.py `
        src/database/repo_helpers.py `
        src/services/event/_anomaly_workbench_service.py `
        src/ui/widgets/anomaly_hypothesis_dialog.py `
        src/ui/widgets/anomaly_attachment_panel.py `
        src/ui/widgets/anomaly_management_page.py `
        scripts/migrate_anomaly_hypotheses_v1.py `
        scripts/audit_phase3_hypotheses.py `
        scripts/sqlite_readonly_fingerprint.py `
        tests/test_hypothesis_phase3.py `
        tests/test_anomaly_workbench_dialogs.py `
        tests/test_anomaly_management_page.py `
        tests/test_attachments_phase2.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 3 focused Ruff gate failed with exit code $LASTEXITCODE."
    }

    & $phase3Python -m pytest -q `
        tests/test_hypothesis_phase3.py `
        tests/test_anomaly_workbench_dialogs.py `
        tests/test_anomaly_management_page.py `
        tests/test_attachments_phase2.py `
        tests/test_database_isolation.py `
        tests/test_anomaly_model_boundary.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 3 focused tests failed with exit code $LASTEXITCODE."
    }
    Write-Host "Phase 3 focused checks passed on disposable database: $phase3VerificationDb"
}
finally {
    Pop-Location
    if ([string]::IsNullOrWhiteSpace($phase3PreviousPythonPath)) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $phase3PreviousPythonPath
    }
    if ([string]::IsNullOrWhiteSpace($phase3PreviousDbPath)) {
        Remove-Item Env:SQE_DB_PATH -ErrorAction SilentlyContinue
    } else {
        $env:SQE_DB_PATH = $phase3PreviousDbPath
    }
    if ([string]::IsNullOrWhiteSpace($phase3PreviousDisposableGuard)) {
        Remove-Item Env:SQE_REQUIRE_DISPOSABLE_DB -ErrorAction SilentlyContinue
    } else {
        $env:SQE_REQUIRE_DISPOSABLE_DB = $phase3PreviousDisposableGuard
    }
    $resolvedScratchRoot = [System.IO.Path]::GetFullPath($phase3ScratchRoot)
    $resolvedVerificationDir = [System.IO.Path]::GetFullPath($phase3VerificationDir)
    if (-not $resolvedVerificationDir.StartsWith(
        $resolvedScratchRoot + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to clean Phase 3 path outside scratch: $resolvedVerificationDir"
    }
    if (Test-Path -LiteralPath $resolvedVerificationDir -PathType Container) {
        Remove-Item -LiteralPath $resolvedVerificationDir -Recurse -Force
    }
    $phase3FormalFingerprintAfter = & $phase3Python $phase3FingerprintScript `
        --digest-only $phase3FormalDb
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to fingerprint the formal database after Phase 3 focused verification."
    }
    if ($phase3FormalFingerprintAfter -ne $phase3FormalFingerprintBefore) {
        throw "Formal database mutation detected during Phase 3 focused verification."
    }
}
