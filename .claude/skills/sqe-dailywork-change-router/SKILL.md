---
name: sqe-dailywork-change-router
description: 把 SQE DailyWork 的變更路由到正確的來源檔案與驗證 gate,在動 PySide6 UI、SQLite 資料契約、services、匯出、docs 或 tests 之前先分類。Use this skill 當要決定改哪裡、跑什麼驗證時。觸發詞包含「route」「change router」「驗證 gate」「PySide6」「SQLite」「data contract」「services」「該改哪」。
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
