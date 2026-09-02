$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$formalDb = Join-Path $repoRoot "data\sqe_v2.db"
$fingerprintScript = Join-Path $repoRoot "scripts\sqlite_readonly_fingerprint.py"
$scratchRoot = Join-Path $repoRoot "scratch\release-visual-baselines"
$verificationDb = Join-Path $scratchRoot "sqe_v2.db"
$targetManifestPath = Join-Path $repoRoot "scripts\qt_probe_targets.json"
$targets = @(
    "appearance-settings",
    "stats-stress",
    "ncr-stats",
    "event-list",
    "empty-states",
    "manager-view"
)
$scales = @("1.0", "1.25", "1.5")

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Release visual baseline refresh requires .venv\Scripts\python.exe"
}

$targetManifest = Get-Content -Raw -LiteralPath $targetManifestPath | ConvertFrom-Json
foreach ($target in $targets) {
    $targetConfig = @($targetManifest.targets | Where-Object { $_.name -eq $target })
    if ($targetConfig.Count -ne 1 -or $targetConfig[0].baseline_required -ne $true) {
        throw "Release visual target is missing or is not baseline-required: $target"
    }
}

$formalFingerprintBefore = & $python $fingerprintScript --digest-only $formalDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to fingerprint the formal database before release visual refresh."
}

New-Item -ItemType Directory -Path $scratchRoot -Force | Out-Null
& $python (Join-Path $repoRoot "scripts\sqlite_backup.py") $formalDb $verificationDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to create the verified disposable database for release visual refresh."
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
        throw "Disposable database initialization failed before release visual refresh."
    }

    foreach ($target in $targets) {
        $targetConfig = @($targetManifest.targets | Where-Object { $_.name -eq $target })[0]
        foreach ($scale in $scales) {
            $probePath = Join-Path $scratchRoot "$target-$scale.png"
            $probeArgs = @(
                (Join-Path $repoRoot "scripts\qt_visual_probe.py"),
                "--target", $target,
                "--scale", $scale,
                "--output", $probePath
            )
            if ($targetConfig.min_width -eq $true) {
                $probeArgs += "--min-width"
            }
            $probeOutput = & $python @probeArgs
            if ($LASTEXITCODE -ne 0) {
                throw "Native release visual probe failed: target=$target scale=$scale"
            }
            $probe = ($probeOutput -join [Environment]::NewLine) | ConvertFrom-Json
            if (
                $probe.visual_trustworthy -ne $true -or
                $probe.qt_platform -ne "windows" -or
                $probe.cjk_font_ok -ne $true -or
                $probe.ncr_cjk_font_ok -ne $true -or
                [int]$probe.qss_unknown_property_warnings -ne 0
            ) {
                throw "Native release visual evidence is not trustworthy: target=$target scale=$scale"
            }
            Write-Host "Trusted release visual probe: target=$target; scale=$scale; platform=$($probe.qt_platform); cjk=$($probe.cjk_font_ok); qss=$($probe.qss_unknown_property_warnings)"
        }
    }

    foreach ($target in $targets) {
        $targetConfig = @($targetManifest.targets | Where-Object { $_.name -eq $target })[0]
        foreach ($scale in $scales) {
            $regressArgs = @(
                (Join-Path $repoRoot "scripts\qt_visual_regress.py"),
                "--target", $target,
                "--scale", $scale,
                "--update"
            )
            if ($targetConfig.min_width -eq $true) {
                $regressArgs += "--min-width"
            }
            $updateOutput = & $python @regressArgs
            if ($LASTEXITCODE -ne 0) {
                $updateOutput | Write-Host
                throw "Release visual baseline update failed: target=$target scale=$scale"
            }
            $updateResult = ($updateOutput -join [Environment]::NewLine) | ConvertFrom-Json
            if ([string]::IsNullOrWhiteSpace([string]$updateResult.updated)) {
                throw "Release visual updater did not confirm the destination: target=$target scale=$scale"
            }
            Write-Host "Updated release visual baseline: target=$target; scale=$scale"
        }
    }

    foreach ($target in $targets) {
        $targetConfig = @($targetManifest.targets | Where-Object { $_.name -eq $target })[0]
        foreach ($scale in $scales) {
            $regressArgs = @(
                (Join-Path $repoRoot "scripts\qt_visual_regress.py"),
                "--target", $target,
                "--scale", $scale
            )
            if ($targetConfig.min_width -eq $true) {
                $regressArgs += "--min-width"
            }
            $readbackOutput = & $python @regressArgs
            if ($LASTEXITCODE -ne 0) {
                $readbackOutput | Write-Host
                throw "Updated release visual baseline did not read back: target=$target scale=$scale"
            }
            $readbackResult = ($readbackOutput -join [Environment]::NewLine) | ConvertFrom-Json
            if ($readbackResult.result -ne "pass") {
                throw "Release visual read-back did not report pass: target=$target scale=$scale"
            }
            Write-Host "Read-back passed: target=$target; scale=$scale"
        }
    }

    Write-Host "Release visual baseline refresh and independent multi-DPI read-back passed."
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
        throw "Unable to fingerprint the formal database after release visual refresh."
    }
    if ($formalFingerprintAfter -ne $formalFingerprintBefore) {
        throw "Formal database mutation detected during release visual refresh."
    }
}
