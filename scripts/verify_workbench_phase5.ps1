param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phase5RepoRoot = Split-Path -Parent $PSScriptRoot
$phase5Python = Join-Path $phase5RepoRoot ".venv\Scripts\python.exe"
$phase5Ruff = Join-Path $phase5RepoRoot ".venv\Scripts\ruff.exe"
$phase5FormalDb = Join-Path $phase5RepoRoot "data\sqe_v2.db"
$phase5FingerprintScript = Join-Path $phase5RepoRoot "scripts\sqlite_readonly_fingerprint.py"
$phase5ScratchRoot = Join-Path $phase5RepoRoot "scratch\phase5-focused"
$phase5VerificationDir = Join-Path $phase5ScratchRoot ([Guid]::NewGuid().ToString("N"))
$phase5VerificationDb = Join-Path $phase5VerificationDir "sqe_v2.db"

if (-not (Test-Path -LiteralPath $phase5Python -PathType Leaf)) {
    throw "Phase 5 Python runtime not found: $phase5Python"
}
if (-not (Test-Path -LiteralPath $phase5Ruff -PathType Leaf)) {
    throw "Phase 5 Ruff runtime not found: $phase5Ruff"
}
if (-not (Test-Path -LiteralPath $phase5FormalDb -PathType Leaf)) {
    throw "Formal source database not found: $phase5FormalDb"
}

$phase5FormalFingerprintBefore = & $phase5Python $phase5FingerprintScript `
    --digest-only $phase5FormalDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to fingerprint the formal database before Phase 5 focused verification."
}
New-Item -ItemType Directory -Path $phase5VerificationDir -Force | Out-Null
& $phase5Python (Join-Path $PSScriptRoot "sqlite_backup.py") `
    $phase5FormalDb $phase5VerificationDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to create the Phase 5 focused disposable database."
}

$phase5PreviousPythonPath = $env:PYTHONPATH
$phase5PreviousDbPath = $env:SQE_DB_PATH
$phase5PreviousDisposableGuard = $env:SQE_REQUIRE_DISPOSABLE_DB
try {
    Push-Location -LiteralPath $phase5RepoRoot
    $env:PYTHONPATH = "$phase5RepoRoot\src;$phase5RepoRoot"
    $env:SQE_DB_PATH = $phase5VerificationDb
    $env:SQE_REQUIRE_DISPOSABLE_DB = "1"
    $env:QT_QPA_PLATFORM = "offscreen"

    Write-Host "[preflight] initialize disposable repeat-issue database"
    & $phase5Python -c @"
from database.connection import initialize_database
initialize_database()
print('workbench phase5 disposable ready')
"@
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 5 disposable preflight failed with exit code $LASTEXITCODE."
    }

    & $phase5Ruff check `
        src/database/anomaly_repeat_repository.py `
        src/services/repeat_issue_service.py `
        src/services/repeat_issue_scoring.py `
        src/ui/widgets/repeat_issues_panel.py `
        tests/test_repeat_issue_phase5.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 5 focused Ruff gate failed with exit code $LASTEXITCODE."
    }

    & $phase5Python -m pytest -q `
        tests/test_repeat_issue_phase5.py `
        tests/test_supplier_360_service.py `
        tests/test_anomaly_management_page.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 5 focused tests failed with exit code $LASTEXITCODE."
    }
    Write-Host "Phase 5 focused checks passed on disposable database: $phase5VerificationDb"
}
finally {
    Pop-Location
    if ([string]::IsNullOrWhiteSpace($phase5PreviousPythonPath)) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $phase5PreviousPythonPath
    }
    if ([string]::IsNullOrWhiteSpace($phase5PreviousDbPath)) {
        Remove-Item Env:SQE_DB_PATH -ErrorAction SilentlyContinue
    } else {
        $env:SQE_DB_PATH = $phase5PreviousDbPath
    }
    if ([string]::IsNullOrWhiteSpace($phase5PreviousDisposableGuard)) {
        Remove-Item Env:SQE_REQUIRE_DISPOSABLE_DB -ErrorAction SilentlyContinue
    } else {
        $env:SQE_REQUIRE_DISPOSABLE_DB = $phase5PreviousDisposableGuard
    }
    $resolvedScratchRoot = [System.IO.Path]::GetFullPath($phase5ScratchRoot)
    $resolvedVerificationDir = [System.IO.Path]::GetFullPath($phase5VerificationDir)
    if (-not $resolvedVerificationDir.StartsWith(
        $resolvedScratchRoot + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to clean Phase 5 path outside scratch: $resolvedVerificationDir"
    }
    if (Test-Path -LiteralPath $resolvedVerificationDir -PathType Container) {
        Remove-Item -LiteralPath $resolvedVerificationDir -Recurse -Force
    }
    $phase5FormalFingerprintAfter = & $phase5Python $phase5FingerprintScript `
        --digest-only $phase5FormalDb
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to fingerprint the formal database after Phase 5 focused verification."
    }
    if ($phase5FormalFingerprintAfter -ne $phase5FormalFingerprintBefore) {
        throw "Formal database mutation detected during Phase 5 focused verification."
    }
}
