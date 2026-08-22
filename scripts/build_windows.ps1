param(
    [switch]$SkipSmoke
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$distDir = Join-Path $repoRoot "dist\SQE_DailyWork"
$exePath = Join-Path $distDir "SQE_DailyWork.exe"

if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
    throw "Missing venv python: $pythonExe"
}

Push-Location $repoRoot
try {
    Write-Host "[1/5] Write build metadata"
    & $pythonExe (Join-Path $repoRoot "scripts\write_build_info.py")
    if ($LASTEXITCODE -ne 0) {
        throw "write_build_info failed"
    }

    Write-Host ""
    Write-Host "[2/5] Ensure PyInstaller is available"
    & $pythonExe -m pip install --disable-pip-version-check pyinstaller | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "pip install pyinstaller failed"
    }

    Write-Host ""
    Write-Host "[3/5] Build onedir distribution"
    if (Test-Path -LiteralPath (Join-Path $repoRoot "build") -PathType Container) {
        Remove-Item -LiteralPath (Join-Path $repoRoot "build") -Recurse -Force
    }
    if (Test-Path -LiteralPath (Join-Path $repoRoot "dist") -PathType Container) {
        Remove-Item -LiteralPath (Join-Path $repoRoot "dist") -Recurse -Force
    }
    & $pythonExe -m PyInstaller (Join-Path $repoRoot "scripts\sqe_dailywork.spec") --noconfirm
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed"
    }
    if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
        throw "Expected executable not found: $exePath"
    }

    Write-Host ""
    Write-Host "[4/6] Write build-info.json into onedir"
    $buildInfoPath = Join-Path $distDir "build-info.json"
    $srcRoot = Join-Path $repoRoot "src"
    $previousPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = @($srcRoot, $repoRoot) -join [System.IO.Path]::PathSeparator
    try {
        $buildInfo = & $pythonExe -c "import json; from build_info import __git_commit__, __build_timestamp__, __dirty_worktree__; from app_version import __version__; print(json.dumps({'version': __version__, 'git_commit': __git_commit__, 'build_timestamp': __build_timestamp__, 'dirty_worktree': __dirty_worktree__}, ensure_ascii=False))"
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to export build-info.json"
        }
    } finally {
        if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
            Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        } else {
            $env:PYTHONPATH = $previousPythonPath
        }
    }
    Set-Content -LiteralPath $buildInfoPath -Value $buildInfo -Encoding UTF8
    Write-Host "Build metadata: $buildInfoPath"

    Write-Host ""
    Write-Host "[5/6] Package portable zip"
    $zipPath = Join-Path $repoRoot "dist\SQE_DailyWork-win64.zip"
    if (Test-Path -LiteralPath $zipPath -PathType Leaf) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path $distDir -DestinationPath $zipPath
    Write-Host "Portable zip: $zipPath"

    if ($SkipSmoke) {
        Write-Host ""
        Write-Host "Build complete (smoke skipped)."
        return
    }

    Write-Host ""
    Write-Host "[6/6] Frozen exe smoke on scratch DB"
    $scratchRoot = Join-Path $distDir "scratch-smoke"
    if (Test-Path -LiteralPath $scratchRoot -PathType Container) {
        Remove-Item -LiteralPath $scratchRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $scratchRoot -Force | Out-Null
    $scratchDb = Join-Path $scratchRoot "sqe_v2.db"

    $env:SQE_DB_PATH = $scratchDb
    $env:SQE_REQUIRE_DISPOSABLE_DB = "1"
    $env:QT_QPA_PLATFORM = "offscreen"
    $env:SQE_TESTING = "1"

    Push-Location $distDir
    try {
        $process = Start-Process `
            -FilePath $exePath `
            -ArgumentList "--smoke-exit" `
            -WorkingDirectory $distDir `
            -PassThru `
            -Wait
        if ($null -eq $process -or $process.ExitCode -ne 0) {
            $code = if ($null -eq $process) { "unknown" } else { $process.ExitCode }
            throw "Frozen exe smoke failed with exit code $code"
        }
        if (-not (Test-Path -LiteralPath $scratchDb -PathType Leaf)) {
            throw "Frozen exe smoke did not create scratch database"
        }
        $markerPath = Join-Path $distDir "logs\smoke_exit.ok"
        if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
            throw "Frozen exe smoke marker missing: $markerPath"
        }
        $markerValue = Get-Content -LiteralPath $markerPath -Raw
        if ([string]::IsNullOrWhiteSpace($markerValue)) {
            throw "Frozen exe smoke marker was empty"
        }
    } finally {
        Pop-Location
    }

    Write-Host ""
    Write-Host "Build and smoke complete: $exePath"
} finally {
    Pop-Location
    Remove-Item Env:SQE_DB_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:SQE_REQUIRE_DISPOSABLE_DB -ErrorAction SilentlyContinue
    Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    Remove-Item Env:SQE_TESTING -ErrorAction SilentlyContinue
}
