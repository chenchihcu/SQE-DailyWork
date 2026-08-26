[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Project Python interpreter not found: $python"
}

$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $repoRoot "src"
    & $python (Join-Path $PSScriptRoot "audit_case_actions_phase1_databases.py")
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 1 formal-database audit found neither the restored pre-migration state nor a safe rollback candidate."
    }
}
finally {
    if ($null -eq $previousPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONPATH = $previousPythonPath
    }
}
