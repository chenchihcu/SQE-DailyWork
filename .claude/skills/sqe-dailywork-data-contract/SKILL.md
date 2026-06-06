---
name: sqe-dailywork-data-contract
description: Use for SQE DailyWork SQLite schema, migrations, visit/anomaly contracts, storage paths, exports, report data, PDF, Excel, and PPTX contract changes.
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
