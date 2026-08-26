$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$formalDb = Join-Path $repoRoot "data\sqe_v2.db"
$fingerprintScript = Join-Path $repoRoot "scripts\sqlite_readonly_fingerprint.py"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Phase 2 visual verification requires .venv\Scripts\python.exe"
}
$formalFingerprintBefore = & $python $fingerprintScript --digest-only $formalDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to fingerprint the formal database before Phase 2 visual verification."
}

$scratchRoot = Join-Path $repoRoot "scratch\phase2-attachments-visual"
$verificationDb = Join-Path $scratchRoot "sqe_v2.db"
New-Item -ItemType Directory -Path $scratchRoot -Force | Out-Null

& $python (Join-Path $repoRoot "scripts\sqlite_backup.py") `
    (Join-Path $repoRoot "data\sqe_v2.db") `
    $verificationDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to create the verified disposable database for Phase 2 visual verification."
}

$previousDbPath = $env:SQE_DB_PATH
$previousDisposableGuard = $env:SQE_REQUIRE_DISPOSABLE_DB
$previousQtPlatform = $env:QT_QPA_PLATFORM
$previousPythonPath = $env:PYTHONPATH

try {
    $env:SQE_DB_PATH = $verificationDb
    $env:SQE_REQUIRE_DISPOSABLE_DB = "1"
    $env:PYTHONPATH = Join-Path $repoRoot "src"
    Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue

    & $python -c @"
from database.connection import initialize_database
from database.repository import anomaly_attachments_contract_ready
from database import connection as conn_mod
initialize_database()
with conn_mod.get_connection() as conn:
    assert anomaly_attachments_contract_ready(conn)
print('attachment contract ready')
"@
    if ($LASTEXITCODE -ne 0) {
        throw "Disposable attachment contract migration failed before visual verification."
    }

    $targets = @("dialog-density", "workbench")
    $scales = @("1.0", "1.25", "1.5")
    foreach ($target in $targets) {
        foreach ($scale in $scales) {
            $probePath = Join-Path $scratchRoot "$target-$scale.png"
            $probeOutput = & $python (Join-Path $repoRoot "scripts\qt_visual_probe.py") `
                --target $target `
                --scale $scale `
                --min-width `
                --output $probePath
            if ($LASTEXITCODE -ne 0) {
                throw "Native $target probe failed at scale $scale."
            }
            $probe = ($probeOutput -join [Environment]::NewLine) | ConvertFrom-Json
            if (
                $probe.visual_trustworthy -ne $true -or
                $probe.qt_platform -ne "windows" -or
                $probe.cjk_font_ok -ne $true -or
                $probe.ncr_cjk_font_ok -ne $true -or
                [int]$probe.qss_unknown_property_warnings -ne 0
            ) {
                throw "Native $target evidence is not trustworthy at scale $scale."
            }
            Write-Host (
                "Trusted probe: target={0}; scale={1}; platform={2}; cjk={3}; qss={4}" -f `
                    $target,
                    $scale,
                    $probe.qt_platform,
                    $probe.cjk_font_ok,
                    $probe.qss_unknown_property_warnings
            )
        }
    }

    foreach ($target in $targets) {
        foreach ($scale in $scales) {
            & $python (Join-Path $repoRoot "scripts\qt_visual_regress.py") `
                --target $target `
                --scale $scale `
                --min-width
            if ($LASTEXITCODE -ne 0) {
                throw "Phase 2 visual regression failed for $target at scale $scale."
            }
        }
    }

    Write-Host "Phase 2 dialog-density and workbench native visual verification passed."
}
finally {
    if ([string]::IsNullOrWhiteSpace($previousDbPath)) {
        Remove-Item Env:SQE_DB_PATH -ErrorAction SilentlyContinue
    } else {
        $env:SQE_DB_PATH = $previousDbPath
    }
    if ([string]::IsNullOrWhiteSpace($previousDisposableGuard)) {
        Remove-Item Env:SQE_REQUIRE_DISPOSABLE_DB -ErrorAction SilentlyContinue
    } else {
        $env:SQE_REQUIRE_DISPOSABLE_DB = $previousDisposableGuard
    }
    if ([string]::IsNullOrWhiteSpace($previousQtPlatform)) {
        Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    } else {
        $env:QT_QPA_PLATFORM = $previousQtPlatform
    }
    if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $previousPythonPath
    }
    $formalFingerprintAfter = & $python $fingerprintScript --digest-only $formalDb
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to fingerprint the formal database after Phase 2 visual verification."
    }
    if ($formalFingerprintAfter -ne $formalFingerprintBefore) {
        throw "Formal database mutation detected during Phase 2 visual verification."
    }
}
