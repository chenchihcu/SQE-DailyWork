. (Join-Path $PSScriptRoot "sqe-dailywork-hook-common.ps1")
$hookInput = Read-SqeDailyWorkHookInput
$text = (ConvertTo-SqeDailyWorkText $hookInput).ToLowerInvariant()
$messages = [System.Collections.Generic.List[string]]::new()

if ($text -match "ui[\\/]|main\.py|qt_visual_probe|theme\.py|widgets[\\/]") {
    $messages.Add("UI surface changed: run focused tests, and use scripts\qt_visual_probe.py for visual/CJK/font evidence.") | Out-Null
}
if ($text -match "database[\\/]|services[\\/]|run_mig\.py|migrate|schema") {
    $messages.Add("Data/service contract changed: run scripts\verify.ps1 when practical, or the closest focused unittest plus residual risk.") | Out-Null
}
if ($text -match "docs[\\/]harness|agents\.md|\.codex[\\/]|\.claude[\\/]|harness_check\.ps1") {
    $messages.Add("Harness or Claude automation changed: run scripts\harness_check.ps1 and inspect Claude hooks/agents/skills manually where possible.") | Out-Null
}

if ($messages.Count -gt 0) {
    Write-SqeDailyWorkSystemMessage ("SQE DailyWork next verification reminder: " + ($messages -join " "))
}
