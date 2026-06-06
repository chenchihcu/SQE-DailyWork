. (Join-Path $PSScriptRoot "sqe-dailywork-hook-common.ps1")
$hookInput = Read-SqeDailyWorkHookInput
$transcriptPath = Get-SqeDailyWorkNestedProperty -Object $hookInput -Path "transcript_path"

if ([string]::IsNullOrWhiteSpace($transcriptPath) -or -not (Test-Path -LiteralPath $transcriptPath -PathType Leaf)) {
    return
}

$recent = ""
try {
    $recent = (Get-Content -LiteralPath $transcriptPath -Tail 80 -ErrorAction Stop) -join "`n"
} catch {
    return
}

$required = @("Changes", "Impact", "Verification", "Residual risk", "Next action")
$missing = @()
foreach ($field in $required) {
    if ($recent -notmatch [regex]::Escape($field)) {
        $missing += $field
    }
}

if ($missing.Count -gt 0) {
    Write-SqeDailyWorkSystemMessage ("SQE DailyWork completion format reminder: include " + ($missing -join ", ") + " unless the user requested a different format.")
}
