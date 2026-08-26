[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python interpreter not found: $python"
}

$activeProcesses = @(
    Get-Process -Name SQE_DailyWork, python, pythonw -ErrorAction SilentlyContinue
)
if ($activeProcesses.Count -gt 0) {
    $processSummary = ($activeProcesses | ForEach-Object {
        "{0}:{1}" -f $_.ProcessName, $_.Id
    }) -join ", "
    throw "Rollback refused while SQE/Python processes are active: $processSummary"
}

$previousPythonPath = $env:PYTHONPATH
$previousRollbackMarker = $env:SQE_CASE_ACTIONS_INCIDENT_ROLLBACK_APPROVED
$previousApplyMarker = $env:SQE_DAILYWORK_CONFIRM_APPLY
try {
    $env:PYTHONPATH = Join-Path $repoRoot "src"
    $env:SQE_CASE_ACTIONS_INCIDENT_ROLLBACK_APPROVED = "1"
    $env:SQE_DAILYWORK_CONFIRM_APPLY = "1"
    & $python (Join-Path $PSScriptRoot "rollback_case_actions_phase1_incident.py")
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 1 formal-database incident rollback failed."
    }
}
finally {
    if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $previousPythonPath
    }
    if ([string]::IsNullOrWhiteSpace($previousRollbackMarker)) {
        Remove-Item Env:SQE_CASE_ACTIONS_INCIDENT_ROLLBACK_APPROVED -ErrorAction SilentlyContinue
    } else {
        $env:SQE_CASE_ACTIONS_INCIDENT_ROLLBACK_APPROVED = $previousRollbackMarker
    }
    if ([string]::IsNullOrWhiteSpace($previousApplyMarker)) {
        Remove-Item Env:SQE_DAILYWORK_CONFIRM_APPLY -ErrorAction SilentlyContinue
    } else {
        $env:SQE_DAILYWORK_CONFIRM_APPLY = $previousApplyMarker
    }
}
