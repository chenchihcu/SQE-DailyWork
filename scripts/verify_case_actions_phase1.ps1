param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phase1RepoRoot = Split-Path -Parent $PSScriptRoot
$phase1Python = Join-Path $phase1RepoRoot ".venv\Scripts\python.exe"
$phase1Ruff = Join-Path $phase1RepoRoot ".venv\Scripts\ruff.exe"
$phase1FormalDb = Join-Path $phase1RepoRoot "data\sqe_v2.db"
$phase1FingerprintScript = Join-Path $phase1RepoRoot "scripts\sqlite_readonly_fingerprint.py"
$phase1ScratchRoot = Join-Path $phase1RepoRoot "scratch\phase1-focused"
$phase1VerificationDir = Join-Path $phase1ScratchRoot ([Guid]::NewGuid().ToString("N"))
$phase1VerificationDb = Join-Path $phase1VerificationDir "sqe_v2.db"

if (-not (Test-Path -LiteralPath $phase1Python -PathType Leaf)) {
    throw "Phase 1 Python runtime not found: $phase1Python"
}
if (-not (Test-Path -LiteralPath $phase1Ruff -PathType Leaf)) {
    throw "Phase 1 Ruff runtime not found: $phase1Ruff"
}
if (-not (Test-Path -LiteralPath $phase1FormalDb -PathType Leaf)) {
    throw "Formal source database not found: $phase1FormalDb"
}

$phase1FormalFingerprintBefore = & $phase1Python $phase1FingerprintScript `
    --digest-only $phase1FormalDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to fingerprint the formal database before Phase 1 focused verification."
}
New-Item -ItemType Directory -Path $phase1VerificationDir -Force | Out-Null
& $phase1Python (Join-Path $PSScriptRoot "sqlite_backup.py") `
    $phase1FormalDb $phase1VerificationDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to create the Phase 1 focused disposable database."
}

$phase1PreviousPythonPath = $env:PYTHONPATH
$phase1PreviousDbPath = $env:SQE_DB_PATH
$phase1PreviousDisposableGuard = $env:SQE_REQUIRE_DISPOSABLE_DB
try {
    Push-Location -LiteralPath $phase1RepoRoot
    $env:PYTHONPATH = "$phase1RepoRoot\src;$phase1RepoRoot"
    $env:SQE_DB_PATH = $phase1VerificationDb
    $env:SQE_REQUIRE_DISPOSABLE_DB = "1"

    Write-Host "[preflight] initialize disposable case_actions_v1"
    & $phase1Python -c "from database.connection import initialize_database; report=initialize_database(); migration=report['case_actions_migration']; assert migration['ready']; print('case_actions_ready', migration['canonical_case_actions'])"
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 1 disposable migration preflight failed with exit code $LASTEXITCODE."
    }

    & $phase1Ruff check `
        src/database/backup.py `
        src/database/repo_helpers.py `
        src/database/case_action_repository.py `
        src/database/connection.py `
        src/services/event/_case_action_service.py `
        src/services/event/_anomaly_workbench_service.py `
        src/ui/widgets/anomaly_action_dialog.py `
        src/ui/widgets/complete_action_dialog.py `
        src/ui/widgets/add_corrective_action_dialog.py `
        src/ui/widgets/complete_corrective_action_dialog.py `
        src/ui/widgets/add_verification_dialog.py `
        src/ui/widgets/anomaly_management_page.py `
        src/ui/widgets/chart_style.py `
        scripts/audit_case_actions_phase1_databases.py `
        scripts/migrate_case_actions_v1.py `
        scripts/qt_visual_probe.py `
        scripts/rollback_case_actions_phase1_incident.py `
        scripts/sqlite_readonly_fingerprint.py `
        tests/test_database_backup.py `
        tests/test_case_actions_phase1.py `
        tests/test_stats_refresh_height_stability.py `
        tests/test_qt_visual_probe_popup_wait.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 1 focused Ruff gate failed with exit code $LASTEXITCODE."
    }

    & $phase1Python -m pytest -q `
        tests/test_database_backup.py `
        tests/test_database_isolation.py `
        tests/test_case_actions_phase1.py `
        tests/test_anomaly_actions_repository.py `
        tests/test_anomaly_actions_service.py `
        tests/test_anomaly_workbench_repository.py `
        tests/test_anomaly_overview_parity.py `
        tests/test_anomaly_management_page.py `
        tests/test_anomaly_action_dialog.py `
        tests/test_anomaly_workbench_dialogs.py `
        tests/test_anomaly_workbench_write_dialogs.py `
        tests/test_anomaly_model_boundary.py `
        tests/test_stats_refresh_height_stability.py `
        tests/test_qt_visual_probe_popup_wait.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 1 focused tests failed with exit code $LASTEXITCODE."
    }
    Write-Host "Phase 1 focused checks passed on disposable database: $phase1VerificationDb"
}
finally {
    Pop-Location
    if ([string]::IsNullOrWhiteSpace($phase1PreviousPythonPath)) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $phase1PreviousPythonPath
    }
    if ([string]::IsNullOrWhiteSpace($phase1PreviousDbPath)) {
        Remove-Item Env:SQE_DB_PATH -ErrorAction SilentlyContinue
    } else {
        $env:SQE_DB_PATH = $phase1PreviousDbPath
    }
    if ([string]::IsNullOrWhiteSpace($phase1PreviousDisposableGuard)) {
        Remove-Item Env:SQE_REQUIRE_DISPOSABLE_DB -ErrorAction SilentlyContinue
    } else {
        $env:SQE_REQUIRE_DISPOSABLE_DB = $phase1PreviousDisposableGuard
    }
    $resolvedScratchRoot = [System.IO.Path]::GetFullPath($phase1ScratchRoot)
    $resolvedVerificationDir = [System.IO.Path]::GetFullPath($phase1VerificationDir)
    if (-not $resolvedVerificationDir.StartsWith(
        $resolvedScratchRoot + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to clean Phase 1 path outside scratch: $resolvedVerificationDir"
    }
    if (Test-Path -LiteralPath $resolvedVerificationDir -PathType Container) {
        Remove-Item -LiteralPath $resolvedVerificationDir -Recurse -Force
    }
    $phase1FormalFingerprintAfter = & $phase1Python $phase1FingerprintScript `
        --digest-only $phase1FormalDb
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to fingerprint the formal database after Phase 1 focused verification."
    }
    if ($phase1FormalFingerprintAfter -ne $phase1FormalFingerprintBefore) {
        throw "Formal database mutation detected during Phase 1 focused verification."
    }
}
