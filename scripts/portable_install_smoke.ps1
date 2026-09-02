param(
    [switch]$SkipBuild,
    [switch]$UseExistingDist,

    [ValidateRange(10, 600)]
    [int]$SmokeTimeoutSeconds = 120
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$distDir = Join-Path $repoRoot "dist\SQE_DailyWork"
$zipPath = Join-Path $repoRoot "dist\SQE_DailyWork-win64.zip"
$buildScript = Join-Path $repoRoot "scripts\build_windows.ps1"
$smokeHelper = Join-Path $repoRoot "scripts\release_smoke_helpers.ps1"

if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    throw "Missing venv python: $pythonExe"
}
if (-not (Test-Path -LiteralPath $smokeHelper -PathType Leaf)) {
    throw "Missing frozen smoke helper: $smokeHelper"
}
. $smokeHelper

$environmentSnapshot = @{}
foreach ($name in @("SQE_DB_PATH", "SQE_REQUIRE_DISPOSABLE_DB", "QT_QPA_PLATFORM", "SQE_TESTING")) {
    $environmentSnapshot[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

Push-Location $repoRoot
try {
    if (-not $UseExistingDist) {
        if ($SkipBuild) {
            throw "SkipBuild requires UseExistingDist when dist/ is missing."
        }
        Write-Host "[1/4] Build Windows onedir + portable zip"
        & $buildScript -SmokeTimeoutSeconds $SmokeTimeoutSeconds
        if ($LASTEXITCODE -ne 0) {
            throw "build_windows.ps1 failed"
        }
    } else {
        Write-Host "[1/4] Using existing dist artifacts"
        if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) {
            throw "Portable zip not found: $zipPath"
        }
    }

    if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) {
        throw "Portable zip not found: $zipPath"
    }

    Write-Host ""
    Write-Host "[2/4] Extract portable zip to scratch temp"
    $extractRoot = Join-Path $repoRoot "scratch\portable-smoke"
    if (Test-Path -LiteralPath $extractRoot -PathType Container) {
        Remove-Item -LiteralPath $extractRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null
    $extractDir = Join-Path $extractRoot "SQE DailyWork portable"
    New-Item -ItemType Directory -Path $extractDir -Force | Out-Null
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDir -Force

    $portableAppDir = Join-Path $extractDir "SQE_DailyWork"
    if (-not (Test-Path -LiteralPath $portableAppDir -PathType Container)) {
        throw "Expected SQE_DailyWork folder inside zip extract: $portableAppDir"
    }

    $exePath = Join-Path $portableAppDir "SQE_DailyWork.exe"
    if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
        throw "Portable executable missing: $exePath"
    }

    $buildInfoPath = Join-Path $portableAppDir "build-info.json"
    if (-not (Test-Path -LiteralPath $buildInfoPath -PathType Leaf)) {
        throw "build-info.json missing in portable tree: $buildInfoPath"
    }
    $buildInfo = Get-Content -LiteralPath $buildInfoPath -Raw | ConvertFrom-Json
    if ([string]::IsNullOrWhiteSpace([string]$buildInfo.version)) {
        throw "build-info.json missing version"
    }
    if ([string]::IsNullOrWhiteSpace([string]$buildInfo.git_commit)) {
        throw "build-info.json missing git_commit"
    }
    if ([string]::IsNullOrWhiteSpace([string]$buildInfo.build_timestamp)) {
        throw "build-info.json missing build_timestamp"
    }
    Write-Host "Portable build-info: version=$($buildInfo.version) commit=$($buildInfo.git_commit)"

    Write-Host ""
    Write-Host "[3/4] Frozen exe smoke from extracted zip (scratch DB)"
    $scratchRoot = Join-Path $portableAppDir "scratch-portable-smoke"
    if (Test-Path -LiteralPath $scratchRoot -PathType Container) {
        Remove-Item -LiteralPath $scratchRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $scratchRoot -Force | Out-Null
    $scratchDb = Join-Path $scratchRoot "sqe_v2.db"

    $env:SQE_DB_PATH = $scratchDb
    $env:SQE_REQUIRE_DISPOSABLE_DB = "1"
    $env:QT_QPA_PLATFORM = "offscreen"
    $env:SQE_TESTING = "1"

    Push-Location $portableAppDir
    try {
        Invoke-FrozenSmokeProcess `
            -ExePath $exePath `
            -WorkingDirectory $portableAppDir `
            -TimeoutSeconds $SmokeTimeoutSeconds `
            -FailureLabel "Portable frozen smoke" | Out-Null
        if (-not (Test-Path -LiteralPath $scratchDb -PathType Leaf)) {
            throw "Portable smoke did not create scratch database"
        }
        $markerPath = Join-Path $portableAppDir "logs\smoke_exit.ok"
        if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
            throw "Portable smoke marker missing: $markerPath"
        }
        $markerValue = Get-Content -LiteralPath $markerPath -Raw
        if ([string]::IsNullOrWhiteSpace($markerValue)) {
            throw "Portable smoke marker was empty"
        }
    } finally {
        Pop-Location
    }

    Write-Host ""
    Write-Host "[4/4] Portable install smoke passed: $portableAppDir"
} finally {
    Pop-Location
    foreach ($name in $environmentSnapshot.Keys) {
        $value = $environmentSnapshot[$name]
        if ($null -eq $value) {
            [Environment]::SetEnvironmentVariable($name, $null, "Process")
        } else {
            [Environment]::SetEnvironmentVariable($name, [string]$value, "Process")
        }
    }
}
