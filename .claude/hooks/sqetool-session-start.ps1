. (Join-Path $PSScriptRoot "sqetool-hook-common.ps1")
$null = Read-SqetoolHookInput

@"
SQETOOL Claude automation context:
- This repo is a single-user local PySide6 + SQLite Supplier Quality Engineering desktop tool.
- Keep changes repo-local; do not modify global Claude/Codex settings for SQETOOL work.
- Use scripts\harness_check.ps1 for harness/config changes.
- Use scripts\verify.ps1 for Python behavior changes when practical.
- QT_QPA_PLATFORM=offscreen is structural smoke only; visual, CJK text, font, and screenshot evidence must use scripts\qt_visual_probe.py on native Windows Qt.
- Data migration, --apply, direct data/*.db edits, and destructive deletes require explicit user approval and verification evidence.
"@ | Write-Output
