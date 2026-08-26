$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$formalDb = Join-Path $repoRoot "data\sqe_v2.db"
$fingerprintScript = Join-Path $repoRoot "scripts\sqlite_readonly_fingerprint.py"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Phase 1 visual baseline refresh requires .venv\Scripts\python.exe"
}
$formalFingerprintBefore = & $python $fingerprintScript --digest-only $formalDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to fingerprint the formal database before visual baseline refresh."
}

$scratchRoot = Join-Path $repoRoot "scratch\phase1-case-actions-baseline"
$verificationDb = Join-Path $scratchRoot "sqe_v2.db"
New-Item -ItemType Directory -Path $scratchRoot -Force | Out-Null

& $python (Join-Path $repoRoot "scripts\sqlite_backup.py") `
    (Join-Path $repoRoot "data\sqe_v2.db") `
    $verificationDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to create the verified disposable database for Phase 1 baseline refresh."
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

    & $python -c "from database.connection import initialize_database; print(initialize_database()['case_actions_migration'])"
    if ($LASTEXITCODE -ne 0) {
        throw "Disposable case_actions_v1 migration failed before baseline refresh."
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
                "Trusted probe before refresh: target={0}; scale={1}; platform={2}; cjk={3}; qss={4}" -f `
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
                --min-width `
                --update
            if ($LASTEXITCODE -ne 0) {
                throw "Phase 1 baseline update failed for $target at scale $scale."
            }
        }
    }

    foreach ($target in $targets) {
        foreach ($scale in $scales) {
            & $python (Join-Path $repoRoot "scripts\qt_visual_regress.py") `
                --target $target `
                --scale $scale `
                --min-width
            if ($LASTEXITCODE -ne 0) {
                throw "Updated Phase 1 baseline did not read back for $target at scale $scale."
            }
        }
    }

    Write-Host "Phase 1 workbench and dialog-density baseline refresh and read-back passed."
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
        throw "Unable to fingerprint the formal database after visual baseline refresh."
    }
    if ($formalFingerprintAfter -ne $formalFingerprintBefore) {
        throw "Formal database mutation detected during visual baseline refresh."
    }
}
