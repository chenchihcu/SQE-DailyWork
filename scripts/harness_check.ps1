Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$failures = [System.Collections.Generic.List[string]]::new()

function Add-Failure {
    param([string]$Message)
    $script:failures.Add($Message) | Out-Null
}

function Join-RepoPath {
    param([string]$RelativePath)
    return (Join-Path $repoRoot $RelativePath)
}

function Require-File {
    param([string]$RelativePath)
    $path = Join-RepoPath $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Add-Failure "Missing file: $RelativePath"
        return $false
    }
    return $true
}

function Require-Directory {
    param([string]$RelativePath)
    $path = Join-RepoPath $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        Add-Failure "Missing directory: $RelativePath"
        return $false
    }
    return $true
}

function Require-Text {
    param(
        [string]$RelativePath,
        [string]$Text,
        [string]$Label
    )
    $path = Join-RepoPath $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Add-Failure "Cannot check ${Label}; missing file: $RelativePath"
        return
    }

    $content = Get-Content -LiteralPath $path -Raw
    if (-not $content.Contains($Text)) {
        Add-Failure "Missing ${Label} in ${RelativePath}: $Text"
    }
}

function Require-SourceBaselineManifest {
    param([string]$RelativePath)
    $requiredTexts = @(
        "Source Baseline Manifest",
        "Purpose",
        "Inspection Commands",
        "Git Boundary Summary",
        "Tracked / Untracked / Ignored Summary",
        "File Classification",
        "Suspicious Items",
        "Baseline Commit Readiness",
        "Role Review Simulation",
        "Residual Risk",
        "Next Action",
        "source_baseline_status",
        "recommended-track-list",
        "recommended-ignore-list",
        "needs-user-decision-list",
        "do-not-track-list",
        "single writer per worktree",
        "local-observed",
        "audit-inference"
    )
    foreach ($text in $requiredTexts) {
        Require-Text $RelativePath $text "source baseline manifest required field"
    }
}

function Require-Json {
    param([string]$RelativePath)
    $path = Join-RepoPath $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Add-Failure "Cannot parse JSON; missing file: $RelativePath"
        return
    }

    try {
        Get-Content -LiteralPath $path -Raw | ConvertFrom-Json | Out-Null
    } catch {
        Add-Failure "Invalid JSON in ${RelativePath}: $($_.Exception.Message)"
    }
}

function Require-CodexRuleExamples {
    param([string]$RelativePath)
    $path = Join-RepoPath $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Add-Failure "Cannot check Codex rule examples; missing file: $RelativePath"
        return
    }

    $content = Get-Content -LiteralPath $path -Raw
    $ruleCount = [regex]::Matches($content, "prefix_rule\(").Count
    $matchCount = [regex]::Matches($content, "(?m)^\s*match\s*=\s*\[").Count
    $notMatchCount = [regex]::Matches($content, "(?m)^\s*not_match\s*=\s*\[").Count

    if ($ruleCount -eq 0) {
        Add-Failure "Codex command policy has no prefix_rule entries: $RelativePath"
    }
    if ($matchCount -ne $ruleCount) {
        Add-Failure "Codex command policy must include one match example per prefix_rule: $RelativePath"
    }
    if ($notMatchCount -ne $ruleCount) {
        Add-Failure "Codex command policy must include one not_match example per prefix_rule: $RelativePath"
    }
}

function Require-LineBudget {
    param(
        [string]$RelativePath,
        [int]$MaxLines,
        [string]$Label
    )
    $path = Join-RepoPath $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Add-Failure "Cannot check ${Label}; missing file: $RelativePath"
        return
    }
    $lineCount = (Get-Content -LiteralPath $path).Count
    if ($lineCount -gt $MaxLines) {
        Add-Failure "${Label} exceeds ${MaxLines} lines: ${RelativePath} has ${lineCount} lines"
    }
}

function Require-ByteBudget {
    param(
        [string]$RelativePath,
        [int]$MaxBytes,
        [string]$Label
    )
    $path = Join-RepoPath $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Add-Failure "Cannot check ${Label}; missing file: $RelativePath"
        return
    }
    $content = Get-Content -LiteralPath $path -Raw
    $byteCount = [System.Text.Encoding]::UTF8.GetByteCount($content)
    if ($byteCount -gt $MaxBytes) {
        Add-Failure "${Label} exceeds ${MaxBytes} bytes: ${RelativePath} has ${byteCount} bytes"
    }
}

function Require-CharBudget {
    param(
        [string]$RelativePath,
        [int]$MaxChars,
        [string]$Label
    )
    $path = Join-RepoPath $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Add-Failure "Cannot check ${Label}; missing file: $RelativePath"
        return
    }
    $content = Get-Content -LiteralPath $path -Raw
    if ($content.Length -gt $MaxChars) {
        Add-Failure "${Label} exceeds ${MaxChars} characters: ${RelativePath} has $($content.Length) characters"
    }
}

function Require-CursorRuleLineBudgets {
    $rulesDir = Join-RepoPath ".cursor\rules"
    if (-not (Test-Path -LiteralPath $rulesDir -PathType Container)) {
        Add-Failure "Cannot check Cursor rule line budgets; missing directory: .cursor\rules"
        return
    }
    Get-ChildItem -LiteralPath $rulesDir -Filter "*.mdc" | ForEach-Object {
        $lineCount = (Get-Content -LiteralPath $_.FullName).Count
        if ($lineCount -gt 500) {
            Add-Failure "Cursor rule exceeds official 500-line guidance: $($_.Name) has ${lineCount} lines"
        }
    }
}

$requiredFiles = @(
    "AGENTS.md",
    "CLAUDE.md",
    ".gitignore",
    ".agents\rules\agents_gateway.md",
    ".cursor\rules\agents_gateway.mdc",
    ".codex\rules\project.rules",
    "scripts\verify.ps1",
    "scripts\harness_check.ps1",
    "scripts\qt_visual_probe.py",
    ".claude\settings.json",
    ".claude\hooks\sqe-dailywork-hook-common.ps1",
    ".claude\hooks\sqe-dailywork-session-start.ps1",
    ".claude\hooks\sqe-dailywork-user-prompt-submit.ps1",
    ".claude\hooks\sqe-dailywork-pre-tool-use.ps1",
    ".claude\hooks\sqe-dailywork-post-tool-use.ps1",
    ".claude\hooks\sqe-dailywork-stop.ps1",
    ".claude\skills\sqe-dailywork-change-router\SKILL.md",
    ".claude\skills\sqe-dailywork-visual-qa\SKILL.md",
    ".claude\skills\sqe-dailywork-data-contract\SKILL.md",
    ".claude\skills\sqe-dailywork-doc-gardening\SKILL.md",
    ".claude\agents\sqe-dailywork-contract-reviewer.md",
    ".claude\agents\sqe-dailywork-qt-visual-reviewer.md",
    ".claude\agents\sqe-dailywork-test-triage.md",
    ".claude\agents\sqe-dailywork-doc-harness-gardener.md",
    "docs\harness\claude-code-automation.md",
    "docs\risk-ledger.md",
    "docs\harness\README.md",
    "docs\harness\ai-rules-compatibility.md",
    "docs\harness\source-baseline-manifest.md",
    "docs\harness\quality-score.md",
    "docs\harness\doc-gardening.md",
    "docs\harness\closed-loop-log.md",
    "docs\exec-plans\README.md",
    "docs\exec-plans\active\README.md",
    "docs\exec-plans\completed\README.md"
)

$requiredDirectories = @(
    "docs\harness",
    ".agents",
    ".agents\rules",
    ".claude",
    ".claude\hooks",
    ".claude\skills",
    ".claude\agents",
    ".claude\skills\sqe-dailywork-change-router",
    ".claude\skills\sqe-dailywork-visual-qa",
    ".claude\skills\sqe-dailywork-data-contract",
    ".claude\skills\sqe-dailywork-doc-gardening",
    "docs\exec-plans",
    "docs\exec-plans\active",
    "docs\exec-plans\completed"
)

foreach ($dir in $requiredDirectories) {
    Require-Directory $dir | Out-Null
}

foreach ($file in $requiredFiles) {
    Require-File $file | Out-Null
}

Require-Text "AGENTS.md" "## Knowledge Map" "repo knowledge map"
Require-Text "AGENTS.md" "## Closed-loop Harness" "closed-loop section"
Require-Text "AGENTS.md" "does not replace or weaken" "global baseline boundary"
Require-Text "AGENTS.md" "scripts/harness_check.ps1" "harness check pointer"
Require-Text "AGENTS.md" "scripts/qt_visual_probe.py" "native Qt visual probe pointer"
Require-Text "AGENTS.md" "offscreen Qt only for structural smoke checks" "offscreen structural-only rule"
Require-Text "AGENTS.md" "QT_QPA_PLATFORM=offscreen" "offscreen platform warning"
Require-Text "AGENTS.md" "screenshots as visual evidence" "offscreen visual evidence boundary"
Require-Text "AGENTS.md" ".cursor/rules/" "existing project rules pointer"
Require-Text "AGENTS.md" "Claude Code automation" "Claude automation knowledge map"
Require-Text "AGENTS.md" "docs/harness/ai-rules-compatibility.md" "AI compatibility pointer"
Require-Text "AGENTS.md" "docs/harness/source-baseline-manifest.md" "source baseline manifest pointer"
Require-Text "AGENTS.md" "completion impact format" "completion impact format"
Require-Text "AGENTS.md" "Residual risk" "residual risk field"
Require-Text "AGENTS.md" "Source-Control Boundary" "source-control boundary rule"
Require-Text "AGENTS.md" "Harness update needed: yes" "learn-before-complete trigger"
Require-Text "AGENTS.md" "/learn" "learn-before-complete workflow"

Require-Text "CLAUDE.md" "@AGENTS.md" "Claude imports AGENTS policy"
Require-Text ".cursor\rules\agents_gateway.mdc" "AGENTS.md" "Cursor gateway points to AGENTS"
Require-Text ".cursor\rules\agents_gateway.mdc" "alwaysApply: true" "Cursor gateway always-on"
Require-Text ".agents\rules\agents_gateway.md" "AGENTS.md" "Antigravity gateway points to AGENTS"
Require-Text ".agents\rules\agents_gateway.md" "New Worktree Mode" "Antigravity worktree preference"
Require-Text ".agents\rules\agents_gateway.md" "Local Mode" "Antigravity local mode boundary"
Require-Text ".agents\rules\agents_gateway.md" "L0/L1/M1/F1/F2" "Antigravity triage pointer"
Require-Text ".agents\rules\agents_gateway.md" "Traditional Chinese" "Antigravity Traditional Chinese output"

Require-Json ".claude\settings.json"
Require-Text ".claude\settings.json" "`"permissions`"" "Claude permissions section"
Require-Text ".claude\settings.json" "`"hooks`"" "Claude hooks section"
Require-Text ".claude\settings.json" "sqe-dailywork-pre-tool-use.ps1" "Claude pre-tool hook"
Require-Text ".claude\settings.json" "sqe-dailywork-post-tool-use.ps1" "Claude post-tool hook"
Require-Text ".claude\settings.json" "sqe-dailywork-user-prompt-submit.ps1" "Claude prompt hook"
Require-Text ".claude\settings.json" "scripts/verify.ps1" "Claude verify ask rule"
Require-Text ".claude\settings.json" "scripts/harness_check.ps1" "Claude harness allow rule"
Require-Text ".claude\settings.json" "data/**" "Claude data deny rule"
Require-Text ".claude\settings.json" "Outputs/**" "Claude output deny rule"

Require-Text ".claude\hooks\sqe-dailywork-session-start.ps1" "SQE DailyWork Claude automation context" "session start context hook"
Require-Text ".claude\hooks\sqe-dailywork-user-prompt-submit.ps1" "scripts\qt_visual_probe.py" "prompt visual reminder"
Require-Text ".claude\hooks\sqe-dailywork-user-prompt-submit.ps1" "MCP is deferred" "prompt MCP deferred reminder"
Require-Text ".claude\hooks\sqe-dailywork-pre-tool-use.ps1" "Write-SqeDailyWorkBlock" "pre-tool block behavior"
Require-Text ".claude\hooks\sqe-dailywork-pre-tool-use.ps1" "--apply" "pre-tool apply guardrail"
Require-Text ".claude\hooks\sqe-dailywork-pre-tool-use.ps1" "data/*.db" "pre-tool DB guardrail"
Require-Text ".claude\hooks\sqe-dailywork-post-tool-use.ps1" "next verification reminder" "post-tool verification reminder"
Require-Text ".claude\hooks\sqe-dailywork-stop.ps1" "Changes" "stop completion format check"
Require-Text ".claude\hooks\sqe-dailywork-hook-common.ps1" "decision = `"block`"" "hook common block shape"

Require-Text ".claude\skills\sqe-dailywork-change-router\SKILL.md" "name: sqe-dailywork-change-router" "change router skill name"
Require-Text ".claude\skills\sqe-dailywork-change-router\SKILL.md" "Verification Selection" "change router verification section"
Require-Text ".claude\skills\sqe-dailywork-visual-qa\SKILL.md" "name: sqe-dailywork-visual-qa" "visual skill name"
Require-Text ".claude\skills\sqe-dailywork-visual-qa\SKILL.md" "Playwright is not visual evidence" "visual Playwright guardrail"
Require-Text ".claude\skills\sqe-dailywork-data-contract\SKILL.md" "name: sqe-dailywork-data-contract" "data contract skill name"
Require-Text ".claude\skills\sqe-dailywork-data-contract\SKILL.md" "database/repository.py" "data contract repository pointer"
Require-Text ".claude\skills\sqe-dailywork-doc-gardening\SKILL.md" "name: sqe-dailywork-doc-gardening" "doc gardening skill name"
Require-Text ".claude\skills\sqe-dailywork-doc-gardening\SKILL.md" "Report-Only Default" "doc gardening report-only rule"

Require-Text ".claude\agents\sqe-dailywork-contract-reviewer.md" "tools: Read, Grep, Glob" "contract reviewer read-only tools"
Require-Text ".claude\agents\sqe-dailywork-qt-visual-reviewer.md" "scripts/qt_visual_probe.py" "visual reviewer probe pointer"
Require-Text ".claude\agents\sqe-dailywork-test-triage.md" "tools: Read, Grep, Glob, Bash" "test triage tools"
Require-Text ".claude\agents\sqe-dailywork-doc-harness-gardener.md" "report-only" "doc gardener report-only"

Require-Text "docs\harness\claude-code-automation.md" "MCP is deferred" "Claude automation MCP deferral"
Require-Text "docs\harness\claude-code-automation.md" "Playwright is not accepted as visual evidence" "Claude automation Playwright guardrail"
Require-Text "docs\harness\claude-code-automation.md" "settings.local.json" "Claude local settings boundary"

Require-Text "docs\harness\README.md" "repo-local system of record" "harness purpose"
Require-Text "docs\harness\README.md" "Qt Visual Evidence" "Qt visual evidence section"
Require-Text "docs\harness\README.md" "native Windows Qt platform" "native Qt visual evidence rule"
Require-Text "docs\harness\ai-rules-compatibility.md" "AI Rules Compatibility Overview" "AI compatibility title"
Require-Text "docs\harness\ai-rules-compatibility.md" "Claim Type" "AI compatibility claim types"
Require-Text "docs\harness\ai-rules-compatibility.md" "Source Register" "AI compatibility source register"
Require-Text "docs\harness\ai-rules-compatibility.md" "Instruction Size Budget" "AI compatibility size budget"
Require-Text "docs\harness\ai-rules-compatibility.md" "project_doc_max_bytes" "Codex instruction byte limit"
Require-Text "docs\harness\ai-rules-compatibility.md" "32 KiB" "Codex default instruction budget"
Require-Text "docs\harness\ai-rules-compatibility.md" "200 lines" "Claude line guidance"
Require-Text "docs\harness\ai-rules-compatibility.md" "500 lines" "Cursor line guidance"
Require-Text "docs\harness\ai-rules-compatibility.md" "12,000 characters" "Antigravity character limit"
Require-Text "docs\harness\ai-rules-compatibility.md" "official" "AI compatibility official claim type"
Require-Text "docs\harness\ai-rules-compatibility.md" "local-observed" "AI compatibility local observed claim type"
Require-Text "docs\harness\ai-rules-compatibility.md" "audit-inference" "AI compatibility audit inference claim type"
Require-Text "docs\harness\ai-rules-compatibility.md" "not verified" "AI compatibility not verified claim type"
Require-Text "docs\harness\ai-rules-compatibility.md" "Source-Control RCA And Extended Risks" "source-control extended risks"
Require-Text "docs\harness\ai-rules-compatibility.md" "Source Control Boundary" "source-control boundary section"
Require-Text "docs\harness\ai-rules-compatibility.md" "Automation Readiness" "automation readiness section"
Require-Text "docs\harness\ai-rules-compatibility.md" "One Writer Protocol" "one-writer protocol section"
Require-Text "docs\harness\ai-rules-compatibility.md" "docs/harness/source-baseline-manifest.md" "source baseline manifest register"
Require-Text "docs\harness\ai-rules-compatibility.md" "one writer per worktree" "one-writer protocol"
Require-Text "docs\harness\ai-rules-compatibility.md" "New Worktree Mode" "Antigravity worktree protocol"
Require-SourceBaselineManifest "docs\harness\source-baseline-manifest.md"
Require-Text "docs\harness\quality-score.md" "Knowledge map" "quality score knowledge row"
Require-Text "docs\harness\doc-gardening.md" "Report only" "report-first automation rule"
Require-Text "docs\harness\doc-gardening.md" "Do not edit files from automation" "automation mutation boundary"
Require-Text "docs\harness\doc-gardening.md" "Changes observed" "automation changes field"
Require-Text "docs\harness\doc-gardening.md" "Impact" "automation impact field"
Require-Text "docs\harness\doc-gardening.md" "Verification status" "automation verification status field"
Require-Text "docs\harness\doc-gardening.md" "Residual risk" "automation residual risk field"
Require-Text "docs\harness\doc-gardening.md" "docs/harness/ai-rules-compatibility.md" "automation compatibility register surface"
Require-Text "docs\harness\doc-gardening.md" "docs/harness/source-baseline-manifest.md" "automation source baseline surface"
Require-Text "docs\harness\doc-gardening.md" "Source baseline manifest" "automation source baseline check"
Require-Text "docs\harness\doc-gardening.md" "Automation self-check" "automation self-check"
Require-Text "docs\harness\doc-gardening.md" ".agents/rules/agents_gateway.md" "automation Antigravity gateway surface"
Require-Text "docs\harness\doc-gardening.md" "AI rules size budget" "automation size budget check"
Require-Text "docs\harness\doc-gardening.md" "Source-control boundary" "automation source-control boundary check"
Require-Text "docs\harness\doc-gardening.md" "WindowsPowerShell" "automation full PowerShell path"
Require-Text "docs\harness\doc-gardening.md" "One-writer safety" "automation one-writer check"

Require-Text "docs\harness\closed-loop-log.md" "Changes:" "completion changes field"
Require-Text "docs\harness\closed-loop-log.md" "Impact:" "completion impact field"
Require-Text "docs\harness\closed-loop-log.md" "Verification:" "completion verification field"
Require-Text "docs\harness\closed-loop-log.md" "Residual risk:" "completion residual risk field"
Require-Text "docs\harness\closed-loop-log.md" "Next action:" "completion next action field"
Require-Text "docs\harness\closed-loop-log.md" "Debug/RCA (when applicable):" "debug RCA section"
Require-Text "docs\harness\closed-loop-log.md" "Observed:" "closed-loop observed field"
Require-Text "docs\harness\closed-loop-log.md" "Root cause:" "closed-loop root cause field"
Require-Text "docs\harness\closed-loop-log.md" "Fix:" "closed-loop fix field"
Require-Text "docs\harness\closed-loop-log.md" "Harness update needed:" "closed-loop harness update field"
Require-Text "docs\harness\closed-loop-log.md" "Destination:" "closed-loop destination field"
Require-Text "docs\harness\closed-loop-log.md" "Qt Visual Evidence Entry" "Qt visual RCA entry"

Require-Text "scripts\verify.ps1" "harness_check.ps1" "verify harness check call"
Require-Text "scripts\verify.ps1" "qt_visual_probe.py" "verify native Qt visual probe call"
Require-Text ".codex\rules\project.rules" "harness_check.ps1" "project rule for harness check"
Require-Text ".codex\rules\project.rules" "scripts/verify.ps1" "project rule for verify"
Require-Text ".codex\rules\project.rules" "qt_visual_probe.py" "project rule for native Qt visual probe"
Require-Text ".codex\rules\project.rules" "match =" "Codex rule match examples"
Require-Text ".codex\rules\project.rules" "not_match =" "Codex rule not_match examples"
Require-Text ".codex\rules\project.rules" "WindowsPowerShell" "Codex rule supports full Windows PowerShell path"
Require-CodexRuleExamples ".codex\rules\project.rules"
Require-ByteBudget "AGENTS.md" 32768 "Codex AGENTS.md size budget"
Require-LineBudget "CLAUDE.md" 200 "Claude CLAUDE.md line budget"
Require-CursorRuleLineBudgets
Require-CharBudget ".agents\rules\agents_gateway.md" 12000 "Antigravity gateway character budget"
Require-Text ".gitignore" ".env" "local environment file is ignored"
Require-Text ".gitignore" "data/" "runtime data directory is ignored"
Require-Text ".gitignore" "Outputs/" "generated Outputs are ignored"
Require-Text ".gitignore" ".claude/settings.local.json" "Claude local settings are ignored"
Require-Text ".gitignore" "!.cursor/rules/**" "Cursor shared rules are versionable"

if ($failures.Count -gt 0) {
    Write-Host "Harness check failed:"
    foreach ($failure in $failures) {
        Write-Host "- $failure"
    }
    exit 1
}

Write-Host "Harness check passed."
