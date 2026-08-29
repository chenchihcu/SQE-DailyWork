param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phase6RepoRoot = Split-Path -Parent $PSScriptRoot
$phase6Python = Join-Path $phase6RepoRoot ".venv\Scripts\python.exe"
$phase6Ruff = Join-Path $phase6RepoRoot ".venv\Scripts\ruff.exe"
$phase6FormalDb = Join-Path $phase6RepoRoot "data\sqe_v2.db"
$phase6FingerprintScript = Join-Path $phase6RepoRoot "scripts\sqlite_readonly_fingerprint.py"
$phase6ScratchRoot = Join-Path $phase6RepoRoot "scratch\phase6-focused"
$phase6VerificationDir = Join-Path $phase6ScratchRoot ([Guid]::NewGuid().ToString("N"))
$phase6VerificationDb = Join-Path $phase6VerificationDir "sqe_v2.db"

if (-not (Test-Path -LiteralPath $phase6Python -PathType Leaf)) {
    throw "Phase 6 Python runtime not found: $phase6Python"
}
if (-not (Test-Path -LiteralPath $phase6Ruff -PathType Leaf)) {
    throw "Phase 6 Ruff runtime not found: $phase6Ruff"
}
if (-not (Test-Path -LiteralPath $phase6FormalDb -PathType Leaf)) {
    throw "Formal source database not found: $phase6FormalDb"
}

$phase6FormalFingerprintBefore = & $phase6Python $phase6FingerprintScript `
    --digest-only $phase6FormalDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to fingerprint the formal database before Phase 6 focused verification."
}
New-Item -ItemType Directory -Path $phase6VerificationDir -Force | Out-Null
& $phase6Python (Join-Path $PSScriptRoot "sqlite_backup.py") `
    $phase6FormalDb $phase6VerificationDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to create the Phase 6 focused disposable database."
}

$phase6PreviousPythonPath = $env:PYTHONPATH
$phase6PreviousDbPath = $env:SQE_DB_PATH
$phase6PreviousDisposableGuard = $env:SQE_REQUIRE_DISPOSABLE_DB
try {
    Push-Location -LiteralPath $phase6RepoRoot
    $env:PYTHONPATH = "$phase6RepoRoot\src;$phase6RepoRoot"
    $env:SQE_DB_PATH = $phase6VerificationDb
    $env:SQE_REQUIRE_DISPOSABLE_DB = "1"
    $env:QT_QPA_PLATFORM = "offscreen"

    Write-Host "[preflight] initialize disposable manager-view database"
    & $phase6Python -c @"
from database.connection import initialize_database
initialize_database()
print('workbench phase6 disposable ready')
"@
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 6 disposable preflight failed with exit code $LASTEXITCODE."
    }

    & $phase6Ruff check `
        src/database/manager_view_repository.py `
        src/services/manager_view_service.py `
        src/ui/widgets/manager_view_page.py `
        tests/test_manager_view_phase6.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 6 focused Ruff gate failed with exit code $LASTEXITCODE."
    }

    & $phase6Python -m pytest -q `
        tests/test_manager_view_phase6.py `
        tests/test_supplier_oriented_ui.py
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 6 focused tests failed with exit code $LASTEXITCODE."
    }
    Write-Host "Phase 6 focused checks passed on disposable database: $phase6VerificationDb"
}
finally {
    Pop-Location
    if ([string]::IsNullOrWhiteSpace($phase6PreviousPythonPath)) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $phase6PreviousPythonPath
    }
    if ([string]::IsNullOrWhiteSpace($phase6PreviousDbPath)) {
        Remove-Item Env:SQE_DB_PATH -ErrorAction SilentlyContinue
    } else {
        $env:SQE_DB_PATH = $phase6PreviousDbPath
    }
    if ([string]::IsNullOrWhiteSpace($phase6PreviousDisposableGuard)) {
        Remove-Item Env:SQE_REQUIRE_DISPOSABLE_DB -ErrorAction SilentlyContinue
    } else {
        $env:SQE_REQUIRE_DISPOSABLE_DB = $phase6PreviousDisposableGuard
    }
    $resolvedScratchRoot = [System.IO.Path]::GetFullPath($phase6ScratchRoot)
    $resolvedVerificationDir = [System.IO.Path]::GetFullPath($phase6VerificationDir)
    if (-not $resolvedVerificationDir.StartsWith(
        $resolvedScratchRoot + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to clean Phase 6 path outside scratch: $resolvedVerificationDir"
    }
    if (Test-Path -LiteralPath $resolvedVerificationDir -PathType Container) {
        Remove-Item -LiteralPath $resolvedVerificationDir -Recurse -Force
    }
    $phase6FormalFingerprintAfter = & $phase6Python $phase6FingerprintScript `
        --digest-only $phase6FormalDb
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to fingerprint the formal database after Phase 6 focused verification."
    }
    if ($phase6FormalFingerprintAfter -ne $phase6FormalFingerprintBefore) {
        throw "Formal database mutation detected during Phase 6 focused verification."
    }
}
