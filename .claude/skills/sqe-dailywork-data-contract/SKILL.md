---
name: sqe-dailywork-data-contract
version: 1.0.0
description: 用於 SQE DailyWork 的 SQLite schema、migration、visit/anomaly 契約、儲存路徑、匯出、報告資料,以及 PDF / Excel / PPTX 契約變更。Use this skill 當要新增或修改上述資料契約時。觸發詞包含「SQLite」「schema」「migration」「data contract」「匯出」「export」「PDF」「Excel」「PPTX」「資料契約」。
allowed-tools: Read, Grep, Glob, Bash
---

# SQE DailyWork Data Contract

Use this skill when a change touches schema, migrations, `src/database/`, `src/services/`, visit/anomaly behavior, exports, reports, or storage paths.

## Source Of Truth

- `README.md` defines product positioning, workflow tabs, outputs, and the v2 database contract.
- `docs/risk-ledger.md` records active data/workflow risks.
- `src/database/repository.py` is the durable write boundary.
- `src/services/event_service.py`, `src/services/event_pdf_exporter.py`, and `src/services/report_service.py` define user-facing exports.

## Contract Guardrails

- Preserve v2 storage paths unless the user explicitly requests a contract change.
- Do not create formal anomaly numbers or closure workflow for lightweight visit defect notes.
- Do not run `run_mig.py`, `--apply`, or direct `data/*.db` manipulation without explicit approval and rollback/verification notes.
- Keep UI terminology, service messages, and docs aligned when visible contract wording changes.

## Verification

- Prefer `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1`.
- If full verification is not practical, run focused tests for the affected contract and name the gap.
- For export changes, inspect the generated artifact path or test output, not only code.

## 何時不要觸發

- 只是要決定「該改哪 / 跑什麼驗證」的跨層路由 → 用 `sqe-dailywork-change-router`
- UI 視覺 / 字體 / 截圖證據 → 用 `sqe-dailywork-visual-qa`
