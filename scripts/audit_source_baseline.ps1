param(
    [string]$OutputDir,
    [switch]$FailOnDoNotTrack
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$gitExe = if (Test-Path -LiteralPath "C:\Program Files\Git\cmd\git.exe") {
    "C:\Program Files\Git\cmd\git.exe"
} else {
    (Get-Command git -ErrorAction Stop).Source
}

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputDir = Join-Path $repoRoot "Outputs\audit\$stamp\source-baseline"
}
$outputPath = [System.IO.Path]::GetFullPath($OutputDir)
$allowedRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "Outputs\audit"))
if (-not $outputPath.StartsWith($allowedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputDir must stay under Outputs\audit: $outputPath"
}
New-Item -ItemType Directory -Path $outputPath -Force | Out-Null

function Invoke-GitLines {
    param([string[]]$Arguments)
    $lines = @(& $gitExe -C $repoRoot @Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
    return @($lines | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

function Get-Classification {
    param([string]$Path)
    if ($Path -match "^(\.playwright-mcp|Outputs|scratch|data|data_backups|build|dist)/") {
        return "do_not_track"
    }
    if ($Path -match "^\.agents/(?!rules/|skills/)") {
        return "do_not_track"
    }
    if ($Path -match "^\.claude/scheduled_tasks\.lock$") {
        return "do_not_track"
    }
    if ($Path -match "^SQE_Quality_Report_.*\.xlsx$") {
        return "do_not_track"
    }
    if ($Path -match "^(\.code_diff\.txt|\.docs_diff\.txt|ORIGINAL_REQUEST\.md|import_err\.txt)$") {
        return "do_not_track"
    }
    if ($Path -match "^(\.venv|\.uv-cache|\.uv-python|__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache)/") {
        return "do_not_track"
    }
    if ($Path -match "^(\.agents/(rules|skills)/|\.claude/(agents|hooks|rules|skills)/|\.codex/(agents|hooks|rules)/|\.cursor/rules/)") {
        return "source"
    }
    if ($Path -match "^(\.codex/hooks\.json|\.claude/(launch\.json|settings\.json)|\.github/|\.opencode/|\.ocx/)") {
        return "source"
    }
    if ($Path -match "^artifacts/.*\.md$") {
        return "source"
    }
    if ($Path -match "^(src|tests|scripts|docs)/") {
        return "source"
    }
    if ($Path -match "^(AGENTS\.md|CLAUDE\.md|CHANGELOG\.md|README\.md|main\.py|run_app\.bat|run_mig\.py|requirements\.txt|pytest\.ini|\.gitignore|\.editorconfig|\.env\.example)$") {
        return "source"
    }
    if ($Path -match "^tests/visual_baseline/") {
        return "source"
    }
    return "needs_review"
}

$statusLines = Invoke-GitLines @("status", "--short", "--untracked-files=all")
$membership = Invoke-GitLines @("ls-files", "--cached", "--others", "--exclude-standard")
$tracked = Invoke-GitLines @("ls-files")
$ignored = Invoke-GitLines @("status", "--short", "--ignored")

$items = [System.Collections.Generic.List[object]]::new()
foreach ($path in $membership) {
    $items.Add([pscustomobject]@{
        path = $path
        classification = Get-Classification $path
        tracked = $tracked.Contains($path)
        exists = Test-Path -LiteralPath (Join-Path $repoRoot $path)
    }) | Out-Null
}
$existingMembership = @($items | Where-Object { $_.exists })

$trackedDoNotTrack = @(
    $tracked | Where-Object {
        (Get-Classification $_) -eq "do_not_track"
    }
)
$needsReview = @($items | Where-Object { $_.classification -eq "needs_review" })

$summary = [pscustomobject]@{
    repo_root = $repoRoot
    inspected_at = (Get-Date).ToString("s")
    membership_count = $existingMembership.Count
    tracked_count = $tracked.Count
    status_count = $statusLines.Count
    tracked_do_not_track_count = $trackedDoNotTrack.Count
    needs_review_count = $needsReview.Count
    status = if ($trackedDoNotTrack.Count -eq 0 -and $needsReview.Count -eq 0) { "pass" } else { "not_pass" }
    tracked_do_not_track = $trackedDoNotTrack
    needs_review = @($needsReview | ForEach-Object { $_.path })
    status_lines = $statusLines
    ignored_lines = $ignored
    items = $items
}

$jsonPath = Join-Path $outputPath "source_baseline_audit.json"
$mdPath = Join-Path $outputPath "source_baseline_audit.md"
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $jsonPath -Encoding utf8

$md = [System.Collections.Generic.List[string]]::new()
$md.Add("# Source Baseline Audit") | Out-Null
$md.Add("") | Out-Null
$md.Add("- Repository: ``$repoRoot``") | Out-Null
$md.Add("- Membership count: ``$($existingMembership.Count)``") | Out-Null
$md.Add("- Tracked do-not-track count: ``$($trackedDoNotTrack.Count)``") | Out-Null
$md.Add("- Needs-review count: ``$($needsReview.Count)``") | Out-Null
$md.Add("- Status: ``$($summary.status)``") | Out-Null
$md.Add("") | Out-Null
$md.Add("## Tracked Do-Not-Track") | Out-Null
if ($trackedDoNotTrack.Count -eq 0) {
    $md.Add("- none") | Out-Null
} else {
    foreach ($path in $trackedDoNotTrack) { $md.Add("- $path") | Out-Null }
}
$md.Add("") | Out-Null
$md.Add("## Needs Review") | Out-Null
if ($needsReview.Count -eq 0) {
    $md.Add("- none") | Out-Null
} else {
    foreach ($item in $needsReview) { $md.Add("- $($item.path)") | Out-Null }
}
$md.Add("") | Out-Null
$md.Add("## Git Status") | Out-Null
foreach ($line in $statusLines) { $md.Add("- ``$line``") | Out-Null }
$md | Set-Content -LiteralPath $mdPath -Encoding utf8

Write-Host "Source baseline audit written:"
Write-Host "- $jsonPath"
Write-Host "- $mdPath"
Write-Host "Status: $($summary.status)"

if ($FailOnDoNotTrack -and $summary.status -ne "pass") {
    exit 1
}
