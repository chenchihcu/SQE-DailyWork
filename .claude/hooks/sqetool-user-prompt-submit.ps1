. (Join-Path $PSScriptRoot "sqetool-hook-common.ps1")
$hookInput = Read-SqetoolHookInput
$text = (ConvertTo-SqetoolText $hookInput).ToLowerInvariant()
$messages = [System.Collections.Generic.List[string]]::new()

if ($text -match "ui|visual|screenshot|font|typography|cjk|qt|pyside|pyside6") {
    $messages.Add("UI or visual work detected: use native Windows Qt evidence through scripts\qt_visual_probe.py; do not treat offscreen screenshots or Playwright as PySide6 visual evidence.") | Out-Null
}
if ($text -match "schema|migration|sqlite|database|data contract|visit_product_sections|visit_defect_notes") {
    $messages.Add("Data contract work detected: read README.md, docs\risk-ledger.md, database\repository.py, and related tests before editing; preserve v2 storage paths unless explicitly changed.") | Out-Null
}
if ($text -match "export|pdf|pptx|excel|report") {
    $messages.Add("Export/report work detected: verify the affected PDF, Excel, or PPTX path and preserve report contract parity.") | Out-Null
}
if ($text -match "delete|remove-item|del /s|rm -rf|--apply") {
    $messages.Add("Destructive or apply-style work detected: require explicit approval, avoid direct data/*.db changes, and report rollback/verification evidence.") | Out-Null
}
if ($text -match "\bmcp\b|model context protocol") {
    $messages.Add("MCP is deferred for SQETOOL phase 1; do not add MCP servers unless the user asks for a new plan.") | Out-Null
}

if ($messages.Count -gt 0) {
    "SQETOOL automation reminders:`n- " + ($messages -join "`n- ") | Write-Output
}
