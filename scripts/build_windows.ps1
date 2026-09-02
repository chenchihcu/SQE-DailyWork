param(
    [switch]$SkipSmoke,

    [ValidateRange(10, 600)]
    [int]$SmokeTimeoutSeconds = 120
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$stageRoot = Join-Path $repoRoot "scratch\release-build"
$stageWorkRoot = Join-Path $stageRoot "work"
$stageDistRoot = Join-Path $stageRoot "dist"
$stageAppDir = Join-Path $stageDistRoot "SQE_DailyWork"
$stageZipPath = Join-Path $stageRoot "SQE_DailyWork-win64.zip"
$finalDistRoot = Join-Path $repoRoot "dist"
$finalAppDir = Join-Path $finalDistRoot "SQE_DailyWork"
$finalZipPath = Join-Path $finalDistRoot "SQE_DailyWork-win64.zip"
$releaseSummaryPath = Join-Path $repoRoot "scratch\release-gate-summary.json"
$previousReleaseSummaryPath = Join-Path $repoRoot "scratch\release-gate-summary.previous.json"
$smokeHelper = Join-Path $PSScriptRoot "release_smoke_helpers.ps1"

function Assert-ChildPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,
        [Parameter(Mandatory = $true)]
        [string]$Candidate
    )

    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $candidateFull = [System.IO.Path]::GetFullPath($Candidate)
    if (-not $candidateFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe path outside intended root: $candidateFull (root=$rootFull)"
    }
    return $candidateFull
}

function Restore-ProcessEnvironment {
    param([hashtable]$Snapshot)
    foreach ($name in $Snapshot.Keys) {
        $value = $Snapshot[$name]
        if ($null -eq $value) {
            [Environment]::SetEnvironmentVariable($name, $null, "Process")
        } else {
            [Environment]::SetEnvironmentVariable($name, [string]$value, "Process")
        }
    }
}

function Archive-VerifiedCurrentArtifact {
    if (-not (Test-Path -LiteralPath $finalZipPath -PathType Leaf)) {
        Write-Host "[rollback] No current zip exists to archive."
        return
    }

    $currentHash = (Get-FileHash -LiteralPath $finalZipPath -Algorithm SHA256).Hash
    $verifiedSummary = $null
    foreach ($summaryPath in @($releaseSummaryPath, $previousReleaseSummaryPath)) {
        if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
            continue
        }
        try {
            $candidate = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
        } catch {
            continue
        }
        $summaryHash = [string]$candidate.artifacts.zip_sha256
        if ($candidate.passed -eq $true -and $summaryHash -eq $currentHash) {
            $verifiedSummary = [pscustomobject]@{
                Path = $summaryPath
                Data = $candidate
            }
            break
        }
    }

    if ($null -eq $verifiedSummary) {
        Write-Warning "[rollback] Current zip is not backed by a matching passed Release summary; it will not be labelled last-known-good."
        return
    }

    $commit = [string]$verifiedSummary.Data.artifacts.build_info.git_commit
    if ([string]::IsNullOrWhiteSpace($commit)) {
        $commit = "unknown"
    }
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $archiveRoot = Join-Path $repoRoot "Outputs\release-archive\$stamp-$commit"
    New-Item -ItemType Directory -Path $archiveRoot -Force | Out-Null
    Copy-Item -LiteralPath $finalZipPath -Destination (Join-Path $archiveRoot "SQE_DailyWork-win64.zip")
    if (Test-Path -LiteralPath (Join-Path $finalAppDir "build-info.json") -PathType Leaf) {
        Copy-Item -LiteralPath (Join-Path $finalAppDir "build-info.json") -Destination $archiveRoot
    }
    Copy-Item -LiteralPath $verifiedSummary.Path -Destination (Join-Path $archiveRoot "release-gate-summary.json")
    Write-Host "[rollback] Archived verified artifact: $archiveRoot"
}

function Assert-PyInstallerCollection {
    $analysisPath = Join-Path $stageWorkRoot "sqe_dailywork\Analysis-00.toc"
    $warningPath = Join-Path $stageWorkRoot "sqe_dailywork\warn-sqe_dailywork.txt"
    $buildLogPath = Join-Path $stageRoot "pyinstaller-build.log"
    if (-not (Test-Path -LiteralPath $analysisPath -PathType Leaf)) {
        throw "PyInstaller analysis manifest missing: $analysisPath"
    }

    $analysisText = Get-Content -LiteralPath $analysisPath -Raw
    if ($analysisText.IndexOf("\.cache\codex-runtimes\", [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
        throw "PyInstaller collected a DLL or data file from the host Codex runtime."
    }
    if ($analysisText -match "(?im)^\s*\('(?:ncr\.tests|tests\.hang_watchdog)(?:[.']|$)" -or
        $analysisText -match "(?i)[\\/]ncr[\\/]tests[\\/]") {
        throw "PyInstaller collected test modules into the release artifact."
    }

    $foreignIcu = Join-Path $stageAppDir "_internal\icuuc.dll"
    if (Test-Path -LiteralPath $foreignIcu -PathType Leaf) {
        throw "Foreign ICU runtime was bundled at _internal\icuuc.dll: $foreignIcu"
    }

    $buildWarnings = @()
    if (Test-Path -LiteralPath $buildLogPath -PathType Leaf) {
        $logLines = @(Get-Content -LiteralPath $buildLogPath)
        $buildWarnings += @(
            $logLines | Where-Object {
                $_ -match "Failed to collect submodules for 'PySide6.scripts" -or
                $_ -match "Library not found: could not resolve '(?:Qt6|icu)" -or
                $_ -match "missing DLLs for"
            }
        )
        $allowedHiddenImports = @("pycparser.lextab", "pycparser.yacctab")
        foreach ($line in $logLines) {
            if ($line -match 'WARNING: Hidden import "([^"]+)" not found!') {
                $missingHiddenImport = $Matches[1]
                if ($missingHiddenImport -notin $allowedHiddenImports) {
                    $buildWarnings += $line
                }
            }
        }
    }

    $requiredModuleWarnings = @()
    $warningLineCount = 0
    if (Test-Path -LiteralPath $warningPath -PathType Leaf) {
        $warningLines = @(Get-Content -LiteralPath $warningPath)
        $warningLineCount = $warningLines.Count
        $requiredPrefixes = @(
            "database", "services", "ui", "ncr", "app_paths", "app_version", "build_info",
            "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "PySide6.QtCharts", "PySide6.QtSvg",
            "openpyxl", "reportlab", "xhtml2pdf", "PIL", "pptx", "dotenv", "pandas"
        )
        # PyInstaller treats a few imported package attributes and explicitly
        # excluded optional/test modules as missing modules. These exact names
        # are not runtime imports in SQE DailyWork and are reviewed here rather
        # than suppressing an entire first-party/dependency namespace.
        $allowedMissingModules = @(
            "pandas.core.internals.Block",
            "pandas.plotting._core",
            "reportlab.platypus.XPreformatted",
            "reportlab.platypus.cleanBlockQuotedText",
            "reportlab.lib.pyHnj",
            "reportlab.local_rl_mods",
            "openpyxl.tests"
        )
        foreach ($line in $warningLines) {
            if ($line -notmatch '^missing module named ') {
                continue
            }
            $missingName = (($line -replace '^missing module named ', '') -split ' - imported by', 2)[0]
            $missingName = $missingName.Trim("'`"")
            if ($missingName -in $allowedMissingModules) {
                continue
            }
            foreach ($requiredPrefix in $requiredPrefixes) {
                if ($missingName -eq $requiredPrefix -or $missingName.StartsWith("$requiredPrefix.")) {
                    $requiredModuleWarnings += $line
                    break
                }
            }
        }
    }

    $actionable = @($buildWarnings) + @($requiredModuleWarnings)
    $audit = [ordered]@{
        passed = ($actionable.Count -eq 0)
        analysis_path = $analysisPath
        warning_path = $warningPath
        warning_line_count = $warningLineCount
        actionable_warnings = @($actionable | ForEach-Object { [string]$_ })
        foreign_runtime_collected = $false
        tests_collected = $false
        root_icu_collected = $false
    }
    $auditPath = Join-Path $stageRoot "pyinstaller-warning-audit.json"
    $audit | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $auditPath -Encoding UTF8
    if ($actionable.Count -ne 0) {
        throw "Actionable PyInstaller warnings remain; see $auditPath"
    }
    Write-Host "PyInstaller warning audit passed (optional warning lines classified=$warningLineCount)."
}

function Promote-StagedArtifact {
    Archive-VerifiedCurrentArtifact
    New-Item -ItemType Directory -Path $finalDistRoot -Force | Out-Null

    $backupRoot = Join-Path $stageRoot "promotion-backup"
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    $backupAppDir = Join-Path $backupRoot "SQE_DailyWork"
    $backupZipPath = Join-Path $backupRoot "SQE_DailyWork-win64.zip"

    try {
        if (Test-Path -LiteralPath $finalAppDir -PathType Container) {
            Move-Item -LiteralPath $finalAppDir -Destination $backupAppDir
        }
        if (Test-Path -LiteralPath $finalZipPath -PathType Leaf) {
            Move-Item -LiteralPath $finalZipPath -Destination $backupZipPath
        }
        Move-Item -LiteralPath $stageAppDir -Destination $finalAppDir
        Move-Item -LiteralPath $stageZipPath -Destination $finalZipPath
    } catch {
        if (Test-Path -LiteralPath $finalAppDir) {
            Remove-Item -LiteralPath $finalAppDir -Recurse -Force
        }
        if (Test-Path -LiteralPath $finalZipPath) {
            Remove-Item -LiteralPath $finalZipPath -Force
        }
        if (Test-Path -LiteralPath $backupAppDir) {
            Move-Item -LiteralPath $backupAppDir -Destination $finalAppDir
        }
        if (Test-Path -LiteralPath $backupZipPath) {
            Move-Item -LiteralPath $backupZipPath -Destination $finalZipPath
        }
        throw
    }
}

if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    throw "Missing venv python: $pythonExe"
}
if (-not (Test-Path -LiteralPath $smokeHelper -PathType Leaf)) {
    throw "Missing frozen smoke helper: $smokeHelper"
}
. $smokeHelper

$safeStageRoot = Assert-ChildPath -Root (Join-Path $repoRoot "scratch") -Candidate $stageRoot
$null = Assert-ChildPath -Root $repoRoot -Candidate $finalAppDir
$null = Assert-ChildPath -Root $repoRoot -Candidate $finalZipPath

$environmentSnapshot = @{}
foreach ($name in @("Path", "SQE_DB_PATH", "SQE_REQUIRE_DISPOSABLE_DB", "QT_QPA_PLATFORM", "SQE_TESTING")) {
    $environmentSnapshot[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

Push-Location $repoRoot
try {
    Write-Host "[1/8] Prepare isolated release-build staging"
    if (Test-Path -LiteralPath $safeStageRoot -PathType Container) {
        Remove-Item -LiteralPath $safeStageRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $stageWorkRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $stageDistRoot -Force | Out-Null

    Write-Host ""
    Write-Host "[2/8] Verify packaging toolchain"
    $toolchain = & $pythonExe -c "import json, sys, PyInstaller, PySide6; print(json.dumps({'python': sys.version.split()[0], 'pyinstaller': PyInstaller.__version__, 'pyside6': PySide6.__version__}))"
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller/PySide6 toolchain is unavailable in .venv"
    }
    Write-Host "Toolchain: $toolchain"

    Write-Host ""
    Write-Host "[3/8] Build onedir with a sanitized native-library PATH"
    $pythonBase = (& $pythonExe -c "import sys; print(sys.base_prefix)").Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($pythonBase)) {
        throw "Unable to resolve Python base prefix"
    }
    $pathParts = @(
        (Split-Path $pythonExe -Parent),
        $pythonBase,
        (Join-Path $pythonBase "DLLs"),
        (Join-Path $env:SystemRoot "System32"),
        $env:SystemRoot
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) -and (Test-Path -LiteralPath $_) }
    $env:Path = ($pathParts -join [System.IO.Path]::PathSeparator)
    $buildLogPath = Join-Path $stageRoot "pyinstaller-build.log"
    $buildStdoutPath = Join-Path $stageRoot "pyinstaller-stdout.log"
    $buildStderrPath = Join-Path $stageRoot "pyinstaller-stderr.log"
    $priorErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell surfaces a native program's stderr as
        # NativeCommandError when ErrorActionPreference=Stop. PyInstaller writes
        # normal INFO progress to stderr, so judge this one pipeline by its real
        # process exit code while still preserving a complete build log.
        $ErrorActionPreference = "Continue"
        & $pythonExe -m PyInstaller `
            (Join-Path $repoRoot "scripts\sqe_dailywork.spec") `
            --noconfirm `
            --clean `
            --workpath $stageWorkRoot `
            --distpath $stageDistRoot `
            1> $buildStdoutPath `
            2> $buildStderrPath
        $pyInstallerExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $priorErrorActionPreference
    }
    $buildLogLines = @()
    if (Test-Path -LiteralPath $buildStdoutPath -PathType Leaf) {
        $buildLogLines += @(Get-Content -LiteralPath $buildStdoutPath)
    }
    if (Test-Path -LiteralPath $buildStderrPath -PathType Leaf) {
        $buildLogLines += @(Get-Content -LiteralPath $buildStderrPath)
    }
    $buildLogLines | Set-Content -LiteralPath $buildLogPath -Encoding UTF8
    $buildLogLines | Out-Host
    $env:Path = [string]$environmentSnapshot["Path"]
    if ($pyInstallerExit -ne 0) {
        throw "PyInstaller build failed with exit code $pyInstallerExit"
    }
    $exePath = Join-Path $stageAppDir "SQE_DailyWork.exe"
    if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
        throw "Expected staged executable not found: $exePath"
    }

    Write-Host ""
    Write-Host "[4/8] Audit collected modules, DLL provenance, and warnings"
    Assert-PyInstallerCollection

    Write-Host ""
    Write-Host "[5/8] Write staged build-info.json"
    $buildInfoPath = Join-Path $stageAppDir "build-info.json"
    & $pythonExe (Join-Path $repoRoot "scripts\write_build_info.py") --output $buildInfoPath
    if ($LASTEXITCODE -ne 0) {
        throw "write_build_info failed"
    }

    Write-Host ""
    Write-Host "[6/8] Package staged portable zip"
    Compress-Archive -Path $stageAppDir -DestinationPath $stageZipPath
    $zipSha256 = (Get-FileHash -LiteralPath $stageZipPath -Algorithm SHA256).Hash
    $buildInfoObject = Get-Content -LiteralPath $buildInfoPath -Raw | ConvertFrom-Json
    $buildInfoObject | Add-Member -NotePropertyName zip_sha256 -NotePropertyValue $zipSha256 -Force
    ($buildInfoObject | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath $buildInfoPath -Encoding UTF8
    Write-Host "Staged zip SHA256: $zipSha256"

    if ($SkipSmoke) {
        Write-Warning "Smoke skipped; candidate remains in staging and is not promoted to dist/."
        Write-Host "Staged app: $stageAppDir"
        Write-Host "Staged zip: $stageZipPath"
        return
    }

    Write-Host ""
    Write-Host "[7/8] Frozen exe smoke on staged scratch DB (timeout=${SmokeTimeoutSeconds}s)"
    $scratchRoot = Join-Path $stageAppDir "scratch-smoke"
    New-Item -ItemType Directory -Path $scratchRoot -Force | Out-Null
    $scratchDb = Join-Path $scratchRoot "sqe_v2.db"
    $env:SQE_DB_PATH = $scratchDb
    $env:SQE_REQUIRE_DISPOSABLE_DB = "1"
    $env:QT_QPA_PLATFORM = "offscreen"
    $env:SQE_TESTING = "1"
    Invoke-FrozenSmokeProcess `
        -ExePath $exePath `
        -WorkingDirectory $stageAppDir `
        -TimeoutSeconds $SmokeTimeoutSeconds `
        -FailureLabel "Frozen exe smoke" | Out-Null
    if (-not (Test-Path -LiteralPath $scratchDb -PathType Leaf)) {
        throw "Frozen exe smoke did not create scratch database"
    }
    $markerPath = Join-Path $stageAppDir "logs\smoke_exit.ok"
    if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
        throw "Frozen exe smoke marker missing: $markerPath"
    }
    $markerValue = Get-Content -LiteralPath $markerPath -Raw
    if ([string]::IsNullOrWhiteSpace($markerValue)) {
        throw "Frozen exe smoke marker was empty"
    }

    Write-Host ""
    Write-Host "[8/8] Promote passing staged artifact"
    Promote-StagedArtifact
    Write-Host "Build and smoke complete: $finalAppDir\SQE_DailyWork.exe"
    Write-Host "Portable zip: $finalZipPath"
    Write-Host "Zip SHA256: $zipSha256"
} finally {
    Pop-Location
    Restore-ProcessEnvironment -Snapshot $environmentSnapshot
}
