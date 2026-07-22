param(
    [string]$PythonExe,
    [ValidateSet("Focused", "Full")]
    [string]$Profile = "Full"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Add-UniqueCandidate {
    param(
        [System.Collections.Generic.List[string]]$List,
        [string]$Value
    )
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return
    }
    if (-not $List.Contains($Value)) {
        $List.Add($Value)
    }
}

function Get-UserProfilePath {
    if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        return $env:USERPROFILE
    }

    $fallback = [Environment]::GetFolderPath("UserProfile")
    if (-not [string]::IsNullOrWhiteSpace($fallback)) {
        return $fallback
    }

    return "C:\Users\user"
}

function Test-PythonRuntime {
    param([string]$PythonPath)

    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
        return $false
    }

    try {
        $previousPythonPath = $env:PYTHONPATH
        $runtimeRepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
        $sitePackages = Join-Path $runtimeRepoRoot ".venv\Lib\site-packages"
        if (Test-Path -LiteralPath $sitePackages -PathType Container) {
            $env:PYTHONPATH = @($sitePackages, $previousPythonPath) -join [System.IO.Path]::PathSeparator
        }
        & $PythonPath -V *> $null
        if ($LASTEXITCODE -ne 0) {
            return $false
        }
        & $PythonPath -c "import PySide6, pandas, openpyxl" *> $null
        if ($LASTEXITCODE -ne 0) {
            return $false
        }
        return $true
    } catch {
        return $false
    } finally {
        if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
            Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        } else {
            $env:PYTHONPATH = $previousPythonPath
        }
    }
}

function Resolve-PythonExe {
    param([string]$RepoRoot, [string]$Override)

    if (-not [string]::IsNullOrWhiteSpace($Override)) {
        if (Test-PythonRuntime -PythonPath $Override) {
            return $Override
        }
        throw "Python override path is invalid or missing required dependencies (PySide6, pandas, openpyxl): $Override"
    }

    $candidates = [System.Collections.Generic.List[string]]::new()
    Add-UniqueCandidate -List $candidates -Value (Join-Path $RepoRoot ".venv\Scripts\python.exe")

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $pythonCmd) {
        Add-UniqueCandidate -List $candidates -Value $pythonCmd.Source
    }

    foreach ($candidate in $candidates) {
        if (Test-PythonRuntime -PythonPath $candidate) {
            return $candidate
        }
    }

    throw "No valid python executable with required dependencies (PySide6, pandas, openpyxl) found. Use -PythonExe <path>."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$resolvedPython = Resolve-PythonExe -RepoRoot $repoRoot -Override $PythonExe

$hadDbPath = Test-Path Env:SQE_DB_PATH
$previousDbPath = $env:SQE_DB_PATH
$hadDisposableGuard = Test-Path Env:SQE_REQUIRE_DISPOSABLE_DB
$previousDisposableGuard = $env:SQE_REQUIRE_DISPOSABLE_DB
$sourceDbPath = if (-not [string]::IsNullOrWhiteSpace($env:SQE_DB_PATH)) {
    [System.IO.Path]::GetFullPath($env:SQE_DB_PATH)
} else {
    Join-Path $repoRoot "data\sqe_v2.db"
}
$verificationRoot = Join-Path $repoRoot "scratch\verify"
$verificationDir = Join-Path $verificationRoot ([Guid]::NewGuid().ToString("N"))
$verificationDb = Join-Path $verificationDir "sqe_v2.db"
New-Item -ItemType Directory -Path $verificationDir -Force | Out-Null

try {
    & $resolvedPython (Join-Path $repoRoot "scripts\sqlite_backup.py") $sourceDbPath $verificationDb
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create verified disposable database for verification"
    }
} catch {
    if (Test-Path -LiteralPath $verificationDir -PathType Container) {
        Remove-Item -LiteralPath $verificationDir -Recurse -Force
    }
    throw
}

$env:SQE_DB_PATH = $verificationDb
$env:SQE_REQUIRE_DISPOSABLE_DB = "1"

Write-Host "Using Python: $resolvedPython"
Write-Host "Verification profile: $Profile"
Write-Host "Disposable database: $verificationDb"

Push-Location $repoRoot
try {
    $sitePackages = Join-Path $repoRoot ".venv\Lib\site-packages"
    $pythonPathEntries = @((Join-Path $repoRoot "src"), $repoRoot)
    if (Test-Path -LiteralPath $sitePackages -PathType Container) {
        $pythonPathEntries += $sitePackages
    }
    $env:PYTHONPATH = $pythonPathEntries -join [System.IO.Path]::PathSeparator
    $env:QT_QPA_PLATFORM = "offscreen"

    Write-Host ""
    Write-Host "[1/6] python -m compileall main.py src scripts run_mig.py tests"
    & $resolvedPython -m compileall main.py src scripts run_mig.py tests
    if ($LASTEXITCODE -ne 0) {
        throw "compileall failed with exit code $LASTEXITCODE"
    }

    Write-Host ""
    if ($Profile -eq "Focused") {
        Write-Host "[2/6] focused unittest safety and contract regressions"
        $focusedPatterns = @(
            "test_database_backup.py",
            "test_database_isolation.py",
            "test_anomaly_transaction_boundaries.py",
            "test_migration_atomicity.py",
            "test_anomaly_repository_invariants.py",
            "test_master_import_service.py",
            "test_date_range_and_export_warnings.py",
            "test_qt_message_handler.py",
            "test_excel_report_custom_range.py",
            "test_form_field_pairing_layout.py",
            "test_form_inline_validation_and_dirty.py"
        )
        foreach ($pattern in $focusedPatterns) {
            & $resolvedPython -m unittest discover -s tests -p $pattern
            if ($LASTEXITCODE -ne 0) {
                throw "focused unittest failed for $pattern with exit code $LASTEXITCODE"
            }
        }
    } else {
        Write-Host "[2/6] python -m unittest discover -s tests"
        & $resolvedPython -m unittest discover -s tests
        if ($LASTEXITCODE -ne 0) {
            throw "unittest failed with exit code $LASTEXITCODE"
        }
    }

    Write-Host ""
    Write-Host "[3/6] offscreen UI structural smoke (not visual evidence)"
    $previousQtPlatform = $env:QT_QPA_PLATFORM
    $env:QT_QPA_PLATFORM = "offscreen"
    try {
        & $resolvedPython -c "from database.connection import initialize_database; from ui.main_window import MainWindow; from PySide6.QtWidgets import QApplication; initialize_database(); app=QApplication.instance() or QApplication([]); w=MainWindow(); print('tabs', w.stack.count()); w.close(); app.processEvents(); print('ui_smoke_ok')"
        if ($LASTEXITCODE -ne 0) {
            throw "offscreen UI smoke failed with exit code $LASTEXITCODE"
        }
    } finally {
        $env:QT_QPA_PLATFORM = $previousQtPlatform
    }

    Write-Host ""
    Write-Host "[4/6] native Qt visual probe belt"
    $previousQtPlatform = $env:QT_QPA_PLATFORM
    try {
        Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
        if ($Profile -eq "Full") {
            & $resolvedPython scripts\qt_visual_belt.py
        } else {
            & $resolvedPython scripts\qt_visual_probe.py --target form-density
        }
        if ($LASTEXITCODE -ne 0) {
            throw "native Qt visual belt failed with exit code $LASTEXITCODE"
        }
    } finally {
        if ([string]::IsNullOrWhiteSpace($previousQtPlatform)) {
            Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
        } else {
            $env:QT_QPA_PLATFORM = $previousQtPlatform
        }
    }

    Write-Host ""
    Write-Host "[5/6] native visual regression"
    if ($Profile -eq "Full") {
        $targetManifest = Get-Content -LiteralPath "scripts\qt_probe_targets.json" -Raw | ConvertFrom-Json
        foreach ($target in $targetManifest.targets) {
            if (-not $target.baseline_required) {
                continue
            }
            $regressArgs = @(
                "scripts\qt_visual_regress.py",
                "--target", [string]$target.name,
                "--scale", "1.0"
            )
            if ($target.min_width) {
                $regressArgs += "--min-width"
            }
            & $resolvedPython @regressArgs
            if ($LASTEXITCODE -ne 0) {
                throw "visual regression failed for $($target.name) with exit code $LASTEXITCODE"
            }
        }
    } else {
        Write-Host "Focused profile skips pixel baselines; native form-density probe already ran."
    }

    Write-Host ""
    Write-Host "[6/6] scripts\harness_check.ps1"
    & (Join-Path $repoRoot "scripts\harness_check.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "harness_check failed with exit code $LASTEXITCODE"
    }

    Write-Host ""
    Write-Host "Verification passed."
} finally {
    Pop-Location
    if ($hadDbPath) {
        $env:SQE_DB_PATH = $previousDbPath
    } else {
        Remove-Item Env:SQE_DB_PATH -ErrorAction SilentlyContinue
    }
    if ($hadDisposableGuard) {
        $env:SQE_REQUIRE_DISPOSABLE_DB = $previousDisposableGuard
    } else {
        Remove-Item Env:SQE_REQUIRE_DISPOSABLE_DB -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $verificationDir -PathType Container) {
        $resolvedVerificationRoot = [System.IO.Path]::GetFullPath($verificationRoot)
        $resolvedVerificationDir = [System.IO.Path]::GetFullPath($verificationDir)
        if (-not $resolvedVerificationDir.StartsWith(
            $resolvedVerificationRoot + [System.IO.Path]::DirectorySeparatorChar,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            throw "Refusing to clean verification path outside scratch/verify: $resolvedVerificationDir"
        }
        Remove-Item -LiteralPath $resolvedVerificationDir -Recurse -Force
    }
}
