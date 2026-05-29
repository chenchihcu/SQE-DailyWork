param(
    [string]$PythonExe
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

    $userProfilePath = Get-UserProfilePath
    $candidates = [System.Collections.Generic.List[string]]::new()
    Add-UniqueCandidate -List $candidates -Value (Join-Path $RepoRoot ".venv\Scripts\python.exe")
    Add-UniqueCandidate -List $candidates -Value (Join-Path $RepoRoot ".uv-python\Scripts\python.exe")
    Add-UniqueCandidate -List $candidates -Value (Join-Path $userProfilePath ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
    Add-UniqueCandidate -List $candidates -Value (Join-Path $userProfilePath "AppData\Local\Python\bin\python.exe")

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

Write-Host "Using Python: $resolvedPython"

Push-Location $repoRoot
try {
    $env:PYTHONPATH = $repoRoot
    $env:QT_QPA_PLATFORM = "offscreen"

    Write-Host ""
    Write-Host "[1/5] python -m compileall main.py database services ui scripts run_mig.py tests"
    & $resolvedPython -m compileall main.py database services ui scripts run_mig.py tests
    if ($LASTEXITCODE -ne 0) {
        throw "compileall failed with exit code $LASTEXITCODE"
    }

    Write-Host ""
    Write-Host "[2/5] python -m unittest discover -s tests"
    & $resolvedPython -m unittest discover -s tests
    if ($LASTEXITCODE -ne 0) {
        throw "unittest failed with exit code $LASTEXITCODE"
    }

    Write-Host ""
    Write-Host "[3/5] offscreen UI structural smoke (not visual evidence)"
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
    Write-Host "[4/5] native Qt visual probe"
    $previousQtPlatform = $env:QT_QPA_PLATFORM
    try {
        Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
        & $resolvedPython scripts\qt_visual_probe.py
        if ($LASTEXITCODE -ne 0) {
            throw "native Qt visual probe failed with exit code $LASTEXITCODE"
        }
    } finally {
        if ([string]::IsNullOrWhiteSpace($previousQtPlatform)) {
            Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
        } else {
            $env:QT_QPA_PLATFORM = $previousQtPlatform
        }
    }

    Write-Host ""
    Write-Host "[5/5] scripts\harness_check.ps1"
    & (Join-Path $repoRoot "scripts\harness_check.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "harness_check failed with exit code $LASTEXITCODE"
    }

    Write-Host ""
    Write-Host "Verification passed."
} finally {
    Pop-Location
}
