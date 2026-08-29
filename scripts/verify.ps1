param(
    [string]$PythonExe,
    [ValidateSet("Focused", "Full", "Coverage", "Soak")]
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

    # A Windows venv launcher can become unusable when its original interpreter
    # path is no longer directly executable by the current shell.  The venv
    # metadata still records the intended base runtime, so use it as a narrow
    # fallback before consulting a PATH-level Python.
    $venvConfig = Join-Path $RepoRoot ".venv\pyvenv.cfg"
    if (Test-Path -LiteralPath $venvConfig -PathType Leaf) {
        $venvHomeLine = Get-Content -LiteralPath $venvConfig |
            Where-Object { $_ -match '^\s*home\s*=\s*(.+?)\s*$' } |
            Select-Object -First 1
        if ($venvHomeLine -match '^\s*home\s*=\s*(.+?)\s*$') {
            $venvHomePath = $Matches[1].Trim()
            Add-UniqueCandidate -List $candidates -Value (Join-Path $venvHomePath "python.exe")
        }
    }

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

function Get-UnittestModuleNames {
    param(
        [string]$RepoRoot,
        [ValidateSet("BeforeEventListRenderStability", "FromEventListRenderStability")]
        [string]$Segment
    )

    $paths = Get-ChildItem -LiteralPath (Join-Path $RepoRoot "tests") -Filter "test_*.py" |
        Sort-Object Name
    $splitName = "test_event_list_widget_render_stability.py"
    switch ($Segment) {
        "BeforeEventListRenderStability" {
            return @(
                $paths |
                    Where-Object { $_.Name -lt $splitName } |
                    ForEach-Object { "tests.$($_.BaseName)" }
            )
        }
        "FromEventListRenderStability" {
            return @(
                $paths |
                    Where-Object { $_.Name -ge $splitName } |
                    ForEach-Object { "tests.$($_.BaseName)" }
            )
        }
    }
}

function Split-ModuleChunks {
    param(
        [object[]]$Modules,
        [int]$ChunkCount = 4
    )

    if ($ChunkCount -le 1 -or $Modules.Count -le 1) {
        return ,@($Modules)
    }

    $size = [math]::Ceiling($Modules.Count / [double]$ChunkCount)
    $chunks = @()
    for ($index = 0; $index -lt $Modules.Count; $index += $size) {
        $end = [math]::Min($index + $size - 1, $Modules.Count - 1)
        $chunks += ,@($Modules[$index..$end])
    }
    return $chunks
}

function Invoke-UnittestDiscoverWindowsSafe {
    param(
        [string]$PythonPath,
        [string]$RepoRoot,
        [ValidateSet("Plain", "CoverageRun", "CoverageAppend")]
        [string]$Mode = "Plain"
    )

    $beforeModules = @(Get-UnittestModuleNames -RepoRoot $RepoRoot -Segment "BeforeEventListRenderStability")
    $afterModules = @(Get-UnittestModuleNames -RepoRoot $RepoRoot -Segment "FromEventListRenderStability")
    if ($Mode -in @("CoverageRun", "CoverageAppend")) {
        $allModules = @($beforeModules + $afterModules)
        $chunks = Split-ModuleChunks -Modules $allModules -ChunkCount 4
    } else {
        $chunks = @($beforeModules, $afterModules)
    }

    for ($index = 0; $index -lt $chunks.Count; $index++) {
        $modules = $chunks[$index]
        $label = $index + 1
        Write-Host "[unittest chunk $label/$($chunks.Count)] $($modules.Count) modules"
        $chunkMode = $Mode
        if ($Mode -eq "CoverageRun" -and $index -gt 0) {
            $chunkMode = "CoverageAppend"
        }
        switch ($chunkMode) {
            "CoverageRun" {
                & $PythonPath -m coverage run -m unittest @modules
            }
            "CoverageAppend" {
                & $PythonPath -m coverage run --append -m unittest @modules
            }
            default {
                & $PythonPath -m unittest @modules
            }
        }
        if ($LASTEXITCODE -ne 0) {
            throw "unittest chunk $label failed with exit code $LASTEXITCODE"
        }
    }
}

function Install-CoverageTool {
    param([string]$PythonPath)

    & $PythonPath -m pip install --disable-pip-version-check coverage *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "pip install coverage failed with exit code $LASTEXITCODE"
    }
}

function Run-CoverageTestSuite {
    param([string]$PythonPath, [string]$RepoRoot)

    $env:PYTHONUNBUFFERED = "1"
    Install-CoverageTool -PythonPath $PythonPath

    $scratchDir = Join-Path $RepoRoot "scratch"
    if (-not (Test-Path -LiteralPath $scratchDir -PathType Container)) {
        New-Item -ItemType Directory -Path $scratchDir -Force | Out-Null
    }

    $coverageData = Join-Path $scratchDir ".coverage"
    if (Test-Path -LiteralPath $coverageData -PathType Leaf) {
        Remove-Item -LiteralPath $coverageData -Force
    }

    Write-Host "[coverage] erase prior data"
    & $PythonPath -m coverage erase
    if ($LASTEXITCODE -ne 0) {
        throw "coverage erase failed with exit code $LASTEXITCODE"
    }

    Write-Host "[coverage] unittest discover -s tests (Windows-safe chunked runner)"
    Invoke-UnittestDiscoverWindowsSafe -PythonPath $PythonPath -RepoRoot $RepoRoot -Mode CoverageRun

    Write-Host "[coverage] ncr.tests.test_core ncr.tests.test_supplier_sync"
    & $PythonPath -m coverage run --append -m unittest ncr.tests.test_core ncr.tests.test_supplier_sync
    if ($LASTEXITCODE -ne 0) {
        throw "coverage ncr unittest failed with exit code $LASTEXITCODE"
    }

    Write-Host "[coverage] pytest module-level regressions"
    & $PythonPath -m pip install --disable-pip-version-check pytest *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "pip install pytest failed with exit code $LASTEXITCODE"
    }
    $pytestModules = @(
        "tests/test_anomaly_folder_creation.py",
        "tests/test_attachment_rename.py",
        "tests/test_table_sorting.py"
    )
    & $PythonPath -m coverage run --append -m pytest @pytestModules -q
    if ($LASTEXITCODE -ne 0) {
        throw "coverage pytest regressions failed with exit code $LASTEXITCODE"
    }
}

function Assert-CoverageBaseline {
    param([string]$PythonPath, [string]$RepoRoot)

    $baselinePath = Join-Path $RepoRoot "docs\release\coverage-baseline.json"
    if (-not (Test-Path -LiteralPath $baselinePath -PathType Leaf)) {
        Write-Host "Coverage baseline file missing; skipping fail-under gate."
        return
    }

    $summaryPath = Join-Path $RepoRoot "scratch\coverage-summary.json"
    if (Test-Path -LiteralPath $summaryPath -PathType Leaf) {
        Remove-Item -LiteralPath $summaryPath -Force
    }
    & $PythonPath -m coverage json -o $summaryPath
    if ($LASTEXITCODE -ne 0) {
        throw "coverage json failed with exit code $LASTEXITCODE"
    }

    & $PythonPath (Join-Path $RepoRoot "scripts\assert_coverage_baseline.py")
    if ($LASTEXITCODE -ne 0) {
        throw "coverage baseline gate failed with exit code $LASTEXITCODE"
    }
}

function Export-CoverageReports {
    param([string]$PythonPath, [string]$RepoRoot)

    $scratchDir = Join-Path $RepoRoot "scratch"
    if (-not (Test-Path -LiteralPath $scratchDir -PathType Container)) {
        New-Item -ItemType Directory -Path $scratchDir -Force | Out-Null
    }

    $xmlPath = Join-Path $scratchDir "coverage.xml"
  if (Test-Path -LiteralPath $xmlPath -PathType Leaf) {
        Remove-Item -LiteralPath $xmlPath -Force
    }
    & $PythonPath -m coverage xml
    if ($LASTEXITCODE -ne 0) {
        throw "coverage xml failed with exit code $LASTEXITCODE"
    }

    $htmlDir = Join-Path $scratchDir "coverage-html"
    if (Test-Path -LiteralPath $htmlDir -PathType Container) {
        Remove-Item -LiteralPath $htmlDir -Recurse -Force
    }
    & $PythonPath -m coverage html
    if ($LASTEXITCODE -ne 0) {
        throw "coverage html failed with exit code $LASTEXITCODE"
    }

    Write-Host "Coverage reports: $xmlPath , $htmlDir"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$resolvedPython = Resolve-PythonExe -RepoRoot $repoRoot -Override $PythonExe
$formalDbPath = Join-Path $repoRoot "data\sqe_v2.db"
$fingerprintScript = Join-Path $repoRoot "scripts\sqlite_readonly_fingerprint.py"
$formalFingerprintBefore = "ABSENT"
if (Test-Path -LiteralPath $formalDbPath -PathType Leaf) {
    $formalFingerprintBefore = & $resolvedPython $fingerprintScript `
        --digest-only $formalDbPath
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to fingerprint the formal database before verification."
    }
}

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

    Write-Host "[preflight] initialize disposable case_actions_v1"
    & $resolvedPython -c "from database.connection import initialize_database; report=initialize_database(); migration=report['case_actions_migration']; assert migration['ready']; print('case_actions_ready', migration['canonical_case_actions'])"
    if ($LASTEXITCODE -ne 0) {
        throw "Disposable case_actions_v1 preflight failed with exit code $LASTEXITCODE"
    }

    if ($Profile -eq "Coverage") {
        Write-Host ""
        Write-Host "[1/3] python -m compileall main.py src scripts run_mig.py tests"
        & $resolvedPython -m compileall main.py src scripts run_mig.py tests
        if ($LASTEXITCODE -ne 0) {
            throw "compileall failed with exit code $LASTEXITCODE"
        }

        Write-Host ""
        Write-Host "[2/3] coverage test suite (unittest + ncr + pytest modules)"
        Run-CoverageTestSuite -PythonPath $resolvedPython -RepoRoot $repoRoot
        Export-CoverageReports -PythonPath $resolvedPython -RepoRoot $repoRoot
        Assert-CoverageBaseline -PythonPath $resolvedPython -RepoRoot $repoRoot

        Write-Host ""
        Write-Host "[3/3] scripts\harness_check.ps1"
        & (Join-Path $repoRoot "scripts\harness_check.ps1")
        if ($LASTEXITCODE -ne 0) {
            throw "harness_check failed with exit code $LASTEXITCODE"
        }

        Write-Host ""
        Write-Host "Coverage verification passed."
        return
    }

    if ($Profile -eq "Soak") {
        if (-not (Test-Path Env:SQE_STABILITY_CYCLES)) {
            $env:SQE_STABILITY_CYCLES = "10"
        }
        Write-Host "Stability cycles: $env:SQE_STABILITY_CYCLES"

        Write-Host ""
        Write-Host "[1/2] stability smoke (tests.test_stability_smoke)"
        & $resolvedPython -m unittest tests.test_stability_smoke
        if ($LASTEXITCODE -ne 0) {
            throw "stability smoke failed with exit code $LASTEXITCODE"
        }

        Write-Host ""
        Write-Host "[2/2] scripts\harness_check.ps1"
        & (Join-Path $repoRoot "scripts\harness_check.ps1")
        if ($LASTEXITCODE -ne 0) {
            throw "harness_check failed with exit code $LASTEXITCODE"
        }

        Write-Host ""
        Write-Host "Soak verification passed."
        return
    }

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
            "test_form_inline_validation_and_dirty.py",
            "test_layout_constants.py",
            "test_list_column_contract.py",
            "test_lightweight_visit_entry_routing.py",
            "test_ncr_embedding_smoke.py",
            "test_surface_usage_structure.py",
            "test_supplier_360_service.py",
            "test_supplier_oriented_ui.py"
        )
        foreach ($pattern in $focusedPatterns) {
            $testModule = [System.IO.Path]::GetFileNameWithoutExtension($pattern)
            if ($pattern -in @(
                    "test_supplier_360_service.py",
                    "test_supplier_oriented_ui.py"
                )) {
                # Import through the tests package so tests/__init__.py can
                # initialize the shared QApplication before Qt widgets load.
                & $resolvedPython -m unittest "tests.$testModule"
            } else {
                & $resolvedPython -m unittest discover -s tests -p $pattern
            }
            if ($LASTEXITCODE -ne 0) {
                throw "focused unittest failed for $pattern with exit code $LASTEXITCODE"
            }
        }
    } else {
        Write-Host "[2/6] python -m unittest discover -s tests (Windows-safe chunked runner)"
        # Keep tests package-qualified so tests/__init__.py initializes the
        # shared QApplication before any PySide6 widget test is imported.
        # Windows offscreen Qt can AV when the full discover suite runs in one
        # process; split at test_event_list_widget_render_stability boundary.
        Invoke-UnittestDiscoverWindowsSafe -PythonPath $resolvedPython -RepoRoot $repoRoot

        Write-Host ""
        Write-Host "[2b/6] python -m unittest ncr.tests.test_core ncr.tests.test_supplier_sync"
        & $resolvedPython -m unittest ncr.tests.test_core ncr.tests.test_supplier_sync
        if ($LASTEXITCODE -ne 0) {
            throw "ncr unittest failed with exit code $LASTEXITCODE"
        }

        Write-Host ""
        Write-Host "[2c/6] pytest module-level regressions"
        & $resolvedPython -m pip install --disable-pip-version-check pytest *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "pip install pytest failed with exit code $LASTEXITCODE"
        }
        $pytestModules = @(
            "tests/test_anomaly_folder_creation.py",
            "tests/test_attachment_rename.py",
            "tests/test_table_sorting.py"
        )
        & $resolvedPython -m pytest @pytestModules -q
        if ($LASTEXITCODE -ne 0) {
            throw "pytest module-level regressions failed with exit code $LASTEXITCODE"
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
    # Tests intentionally exercise writes against the disposable database.
    # Reset it before visual evidence so charts and lists use the same
    # source snapshot as native baseline generation.
    & $resolvedPython (Join-Path $repoRoot "scripts\sqlite_backup.py") $sourceDbPath $verificationDb
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to reset disposable database before visual verification"
    }
    $previousQtPlatform = $env:QT_QPA_PLATFORM
    try {
        Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
        if ($Profile -eq "Full") {
            & $resolvedPython scripts\qt_visual_belt.py
        } else {
            & $resolvedPython scripts\qt_visual_probe.py --target form-density
            if ($LASTEXITCODE -eq 0) {
                & $resolvedPython scripts\qt_visual_probe.py --target event-create --scale 1.0,1.25,1.5 --min-width
            }
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
            foreach ($scale in $targetManifest.required_scales) {
                $regressArgs = @(
                    "scripts\qt_visual_regress.py",
                    "--target", [string]$target.name,
                    "--scale", [string]$scale
                )
                if ($target.min_width) {
                    $regressArgs += "--min-width"
                }

                # Each native probe is allowed to initialize or otherwise touch
                # the disposable database.  Keep every pixel-regression child
                # on the same fresh source snapshot used for baseline capture;
                # otherwise an earlier target/scale can change later geometry
                # without changing the visual contract under test.
                Write-Host "[preflight] reset disposable database before visual regression: $($target.name)@$scale"
                & $resolvedPython (Join-Path $repoRoot "scripts\sqlite_backup.py") $sourceDbPath $verificationDb
                if ($LASTEXITCODE -ne 0) {
                    throw "Unable to reset disposable database before visual regression for $($target.name) at scale $scale"
                }
                & $resolvedPython @regressArgs
                if ($LASTEXITCODE -ne 0) {
                    throw "visual regression failed for $($target.name) at scale $scale with exit code $LASTEXITCODE"
                }
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
    $formalFingerprintAfter = "ABSENT"
    if (Test-Path -LiteralPath $formalDbPath -PathType Leaf) {
        $formalFingerprintAfter = & $resolvedPython $fingerprintScript `
            --digest-only $formalDbPath
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to fingerprint the formal database after verification."
        }
    }
    if ($formalFingerprintAfter -ne $formalFingerprintBefore) {
        throw (
            "Formal database mutation detected during verification: before={0}; after={1}" -f `
                $formalFingerprintBefore,
                $formalFingerprintAfter
        )
    }
}
