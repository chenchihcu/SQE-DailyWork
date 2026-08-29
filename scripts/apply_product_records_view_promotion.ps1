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
$migrateScript = Join-Path $PSScriptRoot "migrate_product_records_view_is_active_v1.py"
$auditScript = Join-Path $PSScriptRoot "audit_product_records_view.py"

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
    throw "product_records VIEW Promotion refused while SQE/Python processes are active: $processSummary"
}

$formalFingerprintBefore = & $python $fingerprintScript --digest-only $formalDb
if ($LASTEXITCODE -ne 0) {
    throw "Unable to fingerprint the formal database before product_records VIEW Promotion."
}

$previousPythonPath = $env:PYTHONPATH
$previousPromotionMarker = $env:SQE_PRODUCT_RECORDS_VIEW_PROMOTION_APPROVED
$previousApplyMarker = $env:SQE_DAILYWORK_CONFIRM_APPLY
try {
    $env:PYTHONPATH = "src;."
    $auditOutput = Join-Path $repoRoot "scratch\product-records-view-audit.json"
    New-Item -ItemType Directory -Path (Split-Path -Parent $auditOutput) -Force | Out-Null

    Write-Host "[preview] product_records_view_is_active_v1"
    & $python $migrateScript --db $formalDb
    if ($LASTEXITCODE -ne 0) {
        throw "product_records VIEW migration preview failed."
    }

    Write-Host "[audit] read-only product_records VIEW baseline"
    & $python $auditScript --db $formalDb --output $auditOutput
    if ($LASTEXITCODE -ne 0) {
        throw "product_records VIEW audit failed."
    }
    Write-Host "Audit report: $auditOutput"

    if (-not $Apply) {
        Write-Host "Dry-run complete. Re-run with -Apply after explicit user authorization (繼續) and set promotion markers."
        return
    }

    $env:SQE_PRODUCT_RECORDS_VIEW_PROMOTION_APPROVED = "1"
    $env:SQE_DAILYWORK_CONFIRM_APPLY = "1"
    Write-Host "[apply] formal product_records VIEW Promotion"
    & $python $migrateScript --db $formalDb --apply
    if ($LASTEXITCODE -ne 0) {
        throw "product_records VIEW migration apply failed. Restore the pre-migration backup; do not use reverse SQL."
    }

    Write-Host "[verify] post-apply focused gate"
    & $python -m unittest tests.test_product_records_view_write_path tests.test_ncr_embedding_smoke -v
    if ($LASTEXITCODE -ne 0) {
        throw "Post-apply product_records focused verification failed."
    }
}
finally {
    if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $previousPythonPath
    }
    if ([string]::IsNullOrWhiteSpace($previousPromotionMarker)) {
        Remove-Item Env:SQE_PRODUCT_RECORDS_VIEW_PROMOTION_APPROVED -ErrorAction SilentlyContinue
    } else {
        $env:SQE_PRODUCT_RECORDS_VIEW_PROMOTION_APPROVED = $previousPromotionMarker
    }
    if ([string]::IsNullOrWhiteSpace($previousApplyMarker)) {
        Remove-Item Env:SQE_DAILYWORK_CONFIRM_APPLY -ErrorAction SilentlyContinue
    } else {
        $env:SQE_DAILYWORK_CONFIRM_APPLY = $previousApplyMarker
    }
    $formalFingerprintAfter = & $python $fingerprintScript --digest-only $formalDb
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to fingerprint the formal database after product_records VIEW Promotion gate."
    }
    if (-not $Apply -and $formalFingerprintAfter -ne $formalFingerprintBefore) {
        throw "Formal database mutation detected during product_records VIEW Promotion dry-run."
    }
}
