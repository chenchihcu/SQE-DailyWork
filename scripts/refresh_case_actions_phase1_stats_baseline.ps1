$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$formalDb = Join-Path $repoRoot "data\sqe_v2.db"
$fingerprintScript = Join-Path $repoRoot "scripts\sqlite_readonly_fingerprint.py"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Phase 1 baseline refresh requires .venv\Scripts\python.exe"
}
$formalFingerprintBefore = & $python $fingerprintScript --digest-only $formalDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to fingerprint the formal database before stats baseline refresh."
}

$scratchRoot = Join-Path $repoRoot "scratch\phase1-stats-baseline"
$verificationDb = Join-Path $scratchRoot "sqe_v2.db"
New-Item -ItemType Directory -Path $scratchRoot -Force | Out-Null

& $python (Join-Path $repoRoot "scripts\sqlite_backup.py") `
    (Join-Path $repoRoot "data\sqe_v2.db") `
    $verificationDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to create the verified disposable database for baseline refresh."
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

    $scales = @("1.0", "1.25", "1.5")
    foreach ($scale in $scales) {
        $probePath = Join-Path $scratchRoot "stats-stress-$scale.png"
        $probeOutput = & $python (Join-Path $repoRoot "scripts\qt_visual_probe.py") `
            --target stats-stress `
            --scale $scale `
            --min-width `
            --output $probePath
        if ($LASTEXITCODE -ne 0) {
            throw "Native stats-stress probe failed at scale $scale."
        }
        $probe = ($probeOutput -join [Environment]::NewLine) | ConvertFrom-Json
        if (
            $probe.visual_trustworthy -ne $true -or
            $probe.qt_platform -ne "windows" -or
            $probe.cjk_font_ok -ne $true -or
            $probe.ncr_cjk_font_ok -ne $true -or
            [int]$probe.qss_unknown_property_warnings -ne 0
        ) {
            throw "Native stats-stress evidence is not trustworthy at scale $scale."
        }
        Write-Host (
            "Trusted stats-stress probe: scale={0}; platform={1}; cjk={2}; qss={3}" -f `
                $scale,
                $probe.qt_platform,
                $probe.cjk_font_ok,
                $probe.qss_unknown_property_warnings
        )
    }

    foreach ($scale in $scales) {
        & $python (Join-Path $repoRoot "scripts\qt_visual_regress.py") `
            --target stats-stress `
            --scale $scale `
            --min-width `
            --update
        if ($LASTEXITCODE -ne 0) {
            throw "stats-stress baseline update failed at scale $scale."
        }
    }

    foreach ($readbackPass in 1..3) {
        foreach ($scale in $scales) {
            & $python (Join-Path $repoRoot "scripts\qt_visual_regress.py") `
                --target stats-stress `
                --scale $scale `
                --min-width
            if ($LASTEXITCODE -ne 0) {
                throw "Updated stats-stress baseline did not read back at scale $scale on independent pass $readbackPass."
            }
        }
    }

    Write-Host "Phase 1 stats-stress baseline refresh and three-pass independent read-back passed."
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
        throw "Unable to fingerprint the formal database after stats baseline refresh."
    }
    if ($formalFingerprintAfter -ne $formalFingerprintBefore) {
        throw "Formal database mutation detected during stats baseline refresh."
    }
}
