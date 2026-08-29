param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phase4RepoRoot = Split-Path -Parent $PSScriptRoot
$phase4Python = Join-Path $phase4RepoRoot ".venv\Scripts\python.exe"
$phase4Ruff = Join-Path $phase4RepoRoot ".venv\Scripts\ruff.exe"
$phase4FormalDb = Join-Path $phase4RepoRoot "data\sqe_v2.db"
$phase4FingerprintScript = Join-Path $phase4RepoRoot "scripts\sqlite_readonly_fingerprint.py"
$phase4ScratchRoot = Join-Path $phase4RepoRoot "scratch\phase4-focused"
$phase4VerificationDir = Join-Path $phase4ScratchRoot ([Guid]::NewGuid().ToString("N"))
$phase4VerificationDb = Join-Path $phase4VerificationDir "sqe_v2.db"

if (-not (Test-Path -LiteralPath $phase4Python -PathType Leaf)) {
    throw "Phase 4 Python runtime not found: $phase4Python"
}
if (-not (Test-Path -LiteralPath $phase4Ruff -PathType Leaf)) {
    throw "Phase 4 Ruff runtime not found: $phase4Ruff"
}
if (-not (Test-Path -LiteralPath $phase4FormalDb -PathType Leaf)) {
    throw "Formal source database not found: $phase4FormalDb"
}

$phase4FormalFingerprintBefore = & $phase4Python $phase4FingerprintScript `
    --digest-only $phase4FormalDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to fingerprint the formal database before Phase 4 focused verification."
}
New-Item -ItemType Directory -Path $phase4VerificationDir -Force | Out-Null
& $phase4Python (Join-Path $PSScriptRoot "sqlite_backup.py") `
    $phase4FormalDb $phase4VerificationDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to create the Phase 4 focused disposable database."
}

$phase4PreviousPythonPath = $env:PYTHONPATH
$phase4PreviousDbPath = $env:SQE_DB_PATH
$phase4PreviousDisposableGuard = $env:SQE_REQUIRE_DISPOSABLE_DB
try {
    Push-Location -LiteralPath $phase4RepoRoot
    $env:PYTHONPATH = "$phase4RepoRoot\src;$phase4RepoRoot"
    $env:SQE_DB_PATH = $phase4VerificationDb
    $env:SQE_REQUIRE_DISPOSABLE_DB = "1"
    $env:QT_QPA_PLATFORM = "offscreen"

    Write-Host "[preflight] initialize disposable workbench database"
    & $phase4Python -c @"
from database.connection import initialize_database
initialize_database()
print('workbench phase4 disposable ready')
"@
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 4 disposable preflight failed with exit code $LASTEXITCODE."
    }

    & $phase4Ruff check `
        src/services/event/_anomaly_service.py `
        src/ui/widgets/anomaly_management_page.py `
        src/ui/widgets/close_anomaly_dialog.py `
        src/ui/widgets/reopen_anomaly_dialog.py `
        src/database/repo_helpers.py `
        tests/test_workbench_phase4.py `
        tests/test_anomaly_management_page.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 4 focused Ruff gate failed with exit code $LASTEXITCODE."
    }

    & $phase4Python -m pytest -q `
        tests/test_workbench_phase4.py `
        tests/test_anomaly_management_page.py `
        tests/test_form_inline_validation_and_dirty.py `
        tests/test_anomaly_category_dropdown.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 4 focused tests failed with exit code $LASTEXITCODE."
    }
    Write-Host "Phase 4 focused checks passed on disposable database: $phase4VerificationDb"
}
finally {
    Pop-Location
    if ([string]::IsNullOrWhiteSpace($phase4PreviousPythonPath)) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $phase4PreviousPythonPath
    }
    if ([string]::IsNullOrWhiteSpace($phase4PreviousDbPath)) {
        Remove-Item Env:SQE_DB_PATH -ErrorAction SilentlyContinue
    } else {
        $env:SQE_DB_PATH = $phase4PreviousDbPath
    }
    if ([string]::IsNullOrWhiteSpace($phase4PreviousDisposableGuard)) {
        Remove-Item Env:SQE_REQUIRE_DISPOSABLE_DB -ErrorAction SilentlyContinue
    } else {
        $env:SQE_REQUIRE_DISPOSABLE_DB = $phase4PreviousDisposableGuard
    }
    $resolvedScratchRoot = [System.IO.Path]::GetFullPath($phase4ScratchRoot)
    $resolvedVerificationDir = [System.IO.Path]::GetFullPath($phase4VerificationDir)
    if (-not $resolvedVerificationDir.StartsWith(
        $resolvedScratchRoot + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to clean Phase 4 path outside scratch: $resolvedVerificationDir"
    }
    if (Test-Path -LiteralPath $resolvedVerificationDir -PathType Container) {
        Remove-Item -LiteralPath $resolvedVerificationDir -Recurse -Force
    }
    $phase4FormalFingerprintAfter = & $phase4Python $phase4FingerprintScript `
        --digest-only $phase4FormalDb
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to fingerprint the formal database after Phase 4 focused verification."
    }
    if ($phase4FormalFingerprintAfter -ne $phase4FormalFingerprintBefore) {
        throw "Formal database mutation detected during Phase 4 focused verification."
    }
}
