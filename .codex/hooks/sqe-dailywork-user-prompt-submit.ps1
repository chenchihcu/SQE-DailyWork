. (Join-Path $PSScriptRoot "sqe-dailywork-hook-common.ps1")
$hookInput = Read-SqeDailyWorkHookInput
$text = (ConvertTo-SqeDailyWorkText $hookInput).ToLowerInvariant()
$messages = [System.Collections.Generic.List[string]]::new()

# 關鍵詞/訊息定義正本: sqe-dailywork-route-keywords.json 的 promptReminders 段
# (2026-07-10 起與 post-tool-use 共用一份資料檔; ui 組訊息的政策出處見 ../rules/visual_evidence_rules.md §1。
#  舊硬編碼 5 組 if-regex 行為由 JSON 逐字承接, 回退比對見 git 歷史。)
$kwPath = Join-Path $PSScriptRoot "sqe-dailywork-route-keywords.json"
$kw = $null
try {
    $kw = Get-Content -Raw -LiteralPath $kwPath -ErrorAction Stop | ConvertFrom-Json
} catch {}
if (-not $kw -or -not $kw.promptReminders) {
    "SQE DailyWork automation reminders:`n- WARNING: sqe-dailywork-route-keywords.json missing or unreadable ($kwPath); prompt reminders inactive until the data file is fixed." | Write-Output
    exit 0
}

foreach ($rule in $kw.promptReminders) {
    if ($text -match $rule.regex) {
        $messages.Add($rule.message) | Out-Null
    }
}

if ($messages.Count -gt 0) {
    "SQE DailyWork automation reminders:`n- " + ($messages -join "`n- ") | Write-Output
}
