param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phase2RepoRoot = Split-Path -Parent $PSScriptRoot
$phase2Python = Join-Path $phase2RepoRoot ".venv\Scripts\python.exe"
$phase2Ruff = Join-Path $phase2RepoRoot ".venv\Scripts\ruff.exe"
$phase2FormalDb = Join-Path $phase2RepoRoot "data\sqe_v2.db"
$phase2FingerprintScript = Join-Path $phase2RepoRoot "scripts\sqlite_readonly_fingerprint.py"
$phase2ScratchRoot = Join-Path $phase2RepoRoot "scratch\phase2-focused"
$phase2VerificationDir = Join-Path $phase2ScratchRoot ([Guid]::NewGuid().ToString("N"))
$phase2VerificationDb = Join-Path $phase2VerificationDir "sqe_v2.db"

if (-not (Test-Path -LiteralPath $phase2Python -PathType Leaf)) {
    throw "Phase 2 Python runtime not found: $phase2Python"
}
if (-not (Test-Path -LiteralPath $phase2Ruff -PathType Leaf)) {
    throw "Phase 2 Ruff runtime not found: $phase2Ruff"
}
if (-not (Test-Path -LiteralPath $phase2FormalDb -PathType Leaf)) {
    throw "Formal source database not found: $phase2FormalDb"
}

$phase2FormalFingerprintBefore = & $phase2Python $phase2FingerprintScript `
    --digest-only $phase2FormalDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to fingerprint the formal database before Phase 2 focused verification."
}
New-Item -ItemType Directory -Path $phase2VerificationDir -Force | Out-Null
& $phase2Python (Join-Path $PSScriptRoot "sqlite_backup.py") `
    $phase2FormalDb $phase2VerificationDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to create the Phase 2 focused disposable database."
}

$phase2PreviousPythonPath = $env:PYTHONPATH
$phase2PreviousDbPath = $env:SQE_DB_PATH
$phase2PreviousDisposableGuard = $env:SQE_REQUIRE_DISPOSABLE_DB
try {
    Push-Location -LiteralPath $phase2RepoRoot
    $env:PYTHONPATH = "$phase2RepoRoot\src;$phase2RepoRoot"
    $env:SQE_DB_PATH = $phase2VerificationDb
    $env:SQE_REQUIRE_DISPOSABLE_DB = "1"

    Write-Host "[preflight] initialize disposable attachment contract"
    & $phase2Python -c @"
from database.connection import initialize_database
from database.repository import anomaly_attachments_contract_ready
from database import connection as conn_mod
with conn_mod.get_connection() as conn:
    assert anomaly_attachments_contract_ready(conn), 'attachment contract not ready'
print('anomaly_attachments_contract_v1 ready')
"@
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 2 disposable attachment preflight failed with exit code $LASTEXITCODE."
    }

    Write-Host "[preview] attachment migration CLI read-only"
    & $phase2Python (Join-Path $PSScriptRoot "migrate_anomaly_attachments_contract_v1.py") `
        --db $phase2VerificationDb
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 2 attachment migration preview failed with exit code $LASTEXITCODE."
    }

    & $phase2Ruff check `
        src/database/repository.py `
        src/database/connection.py `
        src/database/repo_helpers.py `
        src/services/attachment_manager.py `
        src/services/event/_anomaly_workbench_service.py `
        src/ui/widgets/anomaly_attachment_panel.py `
        src/ui/widgets/anomaly_root_cause_dialog.py `
        src/ui/widgets/anomaly_management_page.py `
        scripts/migrate_anomaly_attachments_contract_v1.py `
        scripts/audit_phase2r_attachments.py `
        scripts/sqlite_readonly_fingerprint.py `
        tests/test_attachments_phase2.py `
        tests/test_anomaly_attachment_panel.py `
        tests/test_attachment_manager.py `
        tests/test_anomaly_workbench_repository.py `
        tests/test_anomaly_workbench_dialogs.py `
        tests/test_anomaly_management_page.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 2 focused Ruff gate failed with exit code $LASTEXITCODE."
    }

    & $phase2Python -m pytest -q `
        tests/test_attachments_phase2.py `
        tests/test_anomaly_attachment_panel.py `
        tests/test_attachment_manager.py `
        tests/test_anomaly_workbench_repository.py `
        tests/test_anomaly_workbench_dialogs.py `
        tests/test_anomaly_management_page.py `
        tests/test_database_isolation.py `
        tests/test_anomaly_model_boundary.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 2 focused tests failed with exit code $LASTEXITCODE."
    }
    Write-Host "Phase 2 focused checks passed on disposable database: $phase2VerificationDb"
}
finally {
    Pop-Location
    if ([string]::IsNullOrWhiteSpace($phase2PreviousPythonPath)) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $phase2PreviousPythonPath
    }
    if ([string]::IsNullOrWhiteSpace($phase2PreviousDbPath)) {
        Remove-Item Env:SQE_DB_PATH -ErrorAction SilentlyContinue
    } else {
        $env:SQE_DB_PATH = $phase2PreviousDbPath
    }
    if ([string]::IsNullOrWhiteSpace($phase2PreviousDisposableGuard)) {
        Remove-Item Env:SQE_REQUIRE_DISPOSABLE_DB -ErrorAction SilentlyContinue
    } else {
        $env:SQE_REQUIRE_DISPOSABLE_DB = $phase2PreviousDisposableGuard
    }
    $resolvedScratchRoot = [System.IO.Path]::GetFullPath($phase2ScratchRoot)
    $resolvedVerificationDir = [System.IO.Path]::GetFullPath($phase2VerificationDir)
    if (-not $resolvedVerificationDir.StartsWith(
        $resolvedScratchRoot + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to clean Phase 2 path outside scratch: $resolvedVerificationDir"
    }
    if (Test-Path -LiteralPath $resolvedVerificationDir -PathType Container) {
        Remove-Item -LiteralPath $resolvedVerificationDir -Recurse -Force
    }
    $phase2FormalFingerprintAfter = & $phase2Python $phase2FingerprintScript `
        --digest-only $phase2FormalDb
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to fingerprint the formal database after Phase 2 focused verification."
    }
    if ($phase2FormalFingerprintAfter -ne $phase2FormalFingerprintBefore) {
        throw "Formal database mutation detected during Phase 2 focused verification."
    }
}
