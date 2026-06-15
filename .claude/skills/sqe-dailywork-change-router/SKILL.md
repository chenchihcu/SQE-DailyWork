---
name: sqe-dailywork-change-router
description: Route SQE DailyWork changes to the right source files and verification gate before editing PySide6 UI, SQLite data contracts, services, exports, docs, or tests.
allowed-tools: Read, Grep, Glob
---

# SQE DailyWork Change Router

Use this skill before implementing SQE DailyWork changes that may touch more than one layer.

## Routing Rules

- UI or visible copy: read `AGENTS.md`, `README.md`, `.cursor/rules/agents_gateway.mdc`, and the relevant `src/ui/` widget or `src/ui/popup_i18n.py`.
- Data contract, migration, visit/anomaly behavior, or storage path: read `README.md`, `docs/risk-ledger.md`, `src/database/repository.py`, and focused tests before changing code.
- Service or export behavior: read the related `src/services/` module plus tests for PDF, Excel, PPTX, or event-service behavior.
- Harness, Claude automation, or repo guidance: read `docs/harness/README.md`, `docs/harness/doc-gardening.md`, `scripts/harness_check.ps1`, and this repo's `AGENTS.md`.

## Verification Selection

- Harness/config/docs-only automation changes: run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/harness_check.ps1`.
- Python behavior changes: prefer `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1`.
- UI visual/CJK/font/screenshot work: use `scripts\qt_visual_probe.py` on native Windows Qt; offscreen is structural smoke only.
- If full verification is impractical, run the closest focused unittest and report the residual risk.

## Guardrails

- Do not treat Playwright as visual evidence for this PySide6 desktop app.
- Do not run migration, `--apply`, direct `data/*.db` changes, or destructive cleanup without explicit user approval.
- Keep findings and delivery in `Changes / Impact / Verification / Residual risk / Next action`.
