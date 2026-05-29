# Claude Code Automation (SQETOOL)

This document records the repo-local Claude Code automation layer for SQETOOL. It does not replace `AGENTS.md`, `.cursor/rules/agents_gateway.mdc`, `.agents/rules/agents_gateway.md`, `.codex/rules/project.rules`, or the global Codex baseline.

## Active Layer

- Shared project settings: `.claude/settings.json`.
- Lifecycle hooks: `.claude/hooks/`.
- Project skills: `.claude/skills/`.
- Project subagents: `.claude/agents/`.
- Harness gate: `scripts/harness_check.ps1`.

## Recommended Automation Implemented

- Route SQETOOL changes to the right source-of-truth files before editing.
- Warn or block unsafe command patterns before they run.
- Keep PySide6 visual evidence tied to native Windows Qt through `scripts\qt_visual_probe.py`.
- Keep data contract work tied to `README.md`, `docs/risk-ledger.md`, `database/repository.py`, and focused tests.
- Keep doc gardening report-only unless the user explicitly asks for remediation.
- Keep completion delivery aligned to `Changes / Impact / Verification / Residual risk / Next action`.

## Guardrails For Not-Recommended Items

- MCP is deferred in phase 1. A future read-only SQETOOL inspector MCP may be planned later, but no MCP server is configured here.
- Full `scripts\verify.ps1` is not run automatically after every edit. Hooks only remind the agent when it is the right next gate.
- Playwright is not accepted as visual evidence for this PySide6 desktop app. Use native Qt visual evidence instead.
- Doc gardening must not edit files by default.
- `.claude/settings.local.json` remains personal and must not be copied into shared project settings.
- Destructive deletes, direct `data/*.db` manipulation, migrations, and `--apply` commands require explicit approval and verification evidence.

## Manual Claude Code Checks

- Use `/hooks` to inspect loaded hook configuration.
- Use `/agents` to confirm project subagents are visible.
- Use `/sqetool-visual-qa` and `/sqetool-data-contract` to confirm project skills can be invoked.

## Verification

Run:

```powershell
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\harness_check.ps1
```

For behavior changes, run:

```powershell
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1
```
