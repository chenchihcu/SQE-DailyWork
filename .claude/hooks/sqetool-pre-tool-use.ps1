. (Join-Path $PSScriptRoot "sqetool-hook-common.ps1")
$hookInput = Read-SqetoolHookInput
$commandText = Get-SqetoolCommandText -HookInput $hookInput
$lower = $commandText.ToLowerInvariant()

if (($lower -match "remove-item" -and $lower -match "-recurse") -or
    $lower -match "\brm\s+-rf\b" -or
    $lower -match "\brmdir\s+/s\b" -or
    $lower -match "\bdel\s+/s\b") {
    Write-SqetoolBlock "SQETOOL guardrail: recursive/destructive delete is blocked. Ask the user for explicit approval and verify the resolved target path before deleting."
}

if ($lower -match "taskkill" -and $lower -match "python\.exe" -and $lower -match "/f") {
    Write-SqetoolBlock "SQETOOL guardrail: global forced python.exe termination is blocked. Target a specific known PID only after confirming it belongs to this repo task."
}

if ($lower -match "--apply" -and $lower -notmatch "sqetool_confirm_apply=1") {
    Write-SqetoolBlock "SQETOOL guardrail: --apply commands require an explicit SQETOOL_CONFIRM_APPLY=1 marker after user approval and a rollback/verification note."
}

if (($lower -match "data[\\/].*\.db" -or $lower -match "data.*sqe.*\.db") -and
    ($lower -match "remove|del|copy|move|sqlite|python|powershell|pwsh|cmd")) {
    Write-SqetoolBlock "SQETOOL guardrail: direct data/*.db manipulation is blocked. Use the repository migration/verification path and get explicit approval."
}

if ($lower -match "playwright" -and ($lower -match "screenshot|visual|font|cjk|qt|ui")) {
    Write-SqetoolBlock "SQETOOL guardrail: Playwright is not valid visual evidence for this PySide6 desktop app. Use scripts\qt_visual_probe.py on native Windows Qt."
}
