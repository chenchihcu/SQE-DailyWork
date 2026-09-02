$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$formalDb = Join-Path $repoRoot "data\sqe_v2.db"
$fingerprintScript = Join-Path $repoRoot "scripts\sqlite_readonly_fingerprint.py"
$scratchRoot = Join-Path $repoRoot "scratch\event-create-visual-baseline"
$verificationDb = Join-Path $scratchRoot "sqe_v2.db"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Event-create baseline refresh requires .venv\Scripts\python.exe"
}

$formalFingerprintBefore = & $python $fingerprintScript --digest-only $formalDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to fingerprint the formal database before event-create baseline refresh."
}

New-Item -ItemType Directory -Path $scratchRoot -Force | Out-Null
& $python (Join-Path $repoRoot "scripts\sqlite_backup.py") $formalDb $verificationDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to create the verified disposable database for event-create baseline refresh."
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
        throw "Disposable database initialization failed before event-create baseline refresh."
    }

    $scales = @("1.0", "1.25", "1.5")
    foreach ($scale in $scales) {
        $probePath = Join-Path $scratchRoot "event-create-$scale.png"
        $probeOutput = & $python (Join-Path $repoRoot "scripts\qt_visual_probe.py") `
            --target event-create `
            --scale $scale `
            --min-width `
            --output $probePath
        if ($LASTEXITCODE -ne 0) {
            throw "Native event-create probe failed at scale $scale."
        }
        $probe = ($probeOutput -join [Environment]::NewLine) | ConvertFrom-Json
        if (
            $probe.visual_trustworthy -ne $true -or
            $probe.qt_platform -ne "windows" -or
            $probe.cjk_font_ok -ne $true -or
            $probe.ncr_cjk_font_ok -ne $true -or
            [int]$probe.qss_unknown_property_warnings -ne 0
        ) {
            throw "Native event-create evidence is not trustworthy at scale $scale."
        }
        Write-Host "Trusted event-create probe: scale=$scale; platform=$($probe.qt_platform); cjk=$($probe.cjk_font_ok); qss=$($probe.qss_unknown_property_warnings)"
    }

    foreach ($scale in $scales) {
        & $python (Join-Path $repoRoot "scripts\qt_visual_regress.py") `
            --target event-create `
            --scale $scale `
            --min-width `
            --update
        if ($LASTEXITCODE -ne 0) {
            throw "Event-create baseline update failed at scale $scale."
        }
    }

    foreach ($scale in $scales) {
        & $python (Join-Path $repoRoot "scripts\qt_visual_regress.py") `
            --target event-create `
            --scale $scale `
            --min-width
        if ($LASTEXITCODE -ne 0) {
            throw "Updated event-create baseline did not read back at scale $scale."
        }
    }

    Write-Host "Event-create baseline refresh and independent read-back passed."
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
        throw "Unable to fingerprint the formal database after event-create baseline refresh."
    }
    if ($formalFingerprintAfter -ne $formalFingerprintBefore) {
        throw "Formal database mutation detected during event-create baseline refresh."
    }
}
