[CmdletBinding()]
param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$formalDb = Join-Path $repoRoot "data\sqe_v2.db"
$fingerprintScript = Join-Path $repoRoot "scripts\sqlite_readonly_fingerprint.py"
$migrateScript = Join-Path $PSScriptRoot "migrate_anomaly_attachments_contract_v1.py"
$auditScript = Join-Path $PSScriptRoot "audit_phase2r_attachments.py"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python interpreter not found: $python"
}
if (-not (Test-Path -LiteralPath $formalDb -PathType Leaf)) {
    throw "Formal database not found: $formalDb"
}

$activeProcesses = @(
    Get-Process -Name SQE_DailyWork, python, pythonw -ErrorAction SilentlyContinue
)
if ($activeProcesses.Count -gt 0) {
    $processSummary = ($activeProcesses | ForEach-Object {
        "{0}:{1}" -f $_.ProcessName, $_.Id
    }) -join ", "
    throw "Attachment Promotion refused while SQE/Python processes are active: $processSummary"
}

$formalFingerprintBefore = & $python $fingerprintScript --digest-only $formalDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to fingerprint the formal database before attachment Promotion."
}

$previousPythonPath = $env:PYTHONPATH
$previousPromotionMarker = $env:SQE_ANOMALY_ATTACHMENTS_PROMOTION_APPROVED
$previousApplyMarker = $env:SQE_DAILYWORK_CONFIRM_APPLY
try {
    $env:PYTHONPATH = Join-Path $repoRoot "src"
    $auditOutput = Join-Path $repoRoot "scratch\phase2r-attachment-audit.json"
    New-Item -ItemType Directory -Path (Split-Path -Parent $auditOutput) -Force | Out-Null

    Write-Host "[preview] anomaly_attachments_contract_v1"
    & $python $migrateScript --db $formalDb
    if ($LASTEXITCODE -ne 0) {
        throw "Attachment migration preview failed."
    }

    Write-Host "[audit] read-only attachment baseline"
    & $python $auditScript --db $formalDb --output $auditOutput
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 2R attachment audit failed."
    }
    Write-Host "Audit report: $auditOutput"

    if (-not $Apply) {
        Write-Host "Dry-run complete. Re-run with -Apply after explicit user authorization (繼續) and set promotion markers."
        return
    }

    $env:SQE_ANOMALY_ATTACHMENTS_PROMOTION_APPROVED = "1"
    $env:SQE_DAILYWORK_CONFIRM_APPLY = "1"
    Write-Host "[apply] formal attachment Promotion"
    & $python $migrateScript --db $formalDb --apply
    if ($LASTEXITCODE -ne 0) {
        throw "Attachment migration apply failed. Restore the pre-migration backup; do not use reverse SQL."
    }

    Write-Host "[verify] post-apply focused gate"
    & (Join-Path $PSScriptRoot "verify_attachments_phase2.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "Post-apply Phase 2 focused verification failed."
    }
}
finally {
    if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $previousPythonPath
    }
    if ([string]::IsNullOrWhiteSpace($previousPromotionMarker)) {
        Remove-Item Env:SQE_ANOMALY_ATTACHMENTS_PROMOTION_APPROVED -ErrorAction SilentlyContinue
    } else {
        $env:SQE_ANOMALY_ATTACHMENTS_PROMOTION_APPROVED = $previousPromotionMarker
    }
    if ([string]::IsNullOrWhiteSpace($previousApplyMarker)) {
        Remove-Item Env:SQE_DAILYWORK_CONFIRM_APPLY -ErrorAction SilentlyContinue
    } else {
        $env:SQE_DAILYWORK_CONFIRM_APPLY = $previousApplyMarker
    }
    $formalFingerprintAfter = & $python $fingerprintScript --digest-only $formalDb
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to fingerprint the formal database after attachment Promotion gate."
    }
    if (-not $Apply -and $formalFingerprintAfter -ne $formalFingerprintBefore) {
        throw "Formal database mutation detected during attachment Promotion dry-run."
    }
}
