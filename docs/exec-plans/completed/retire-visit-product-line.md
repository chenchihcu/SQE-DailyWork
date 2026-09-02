# Retire visit product line

Plan status: completed

## Goal

Remove all product UI surfaces for supplier visits while preserving legacy SQLite
schema (`visits`, `visit_defect_notes`, `anomalies.visit_id`).

## Changes

- Anomaly form: removed 風險與參考 / 訪廠關聯 UI, mixin, and visit preferences (v10).
- Event query: scopes reduced to 單獨異常 / 已結案; no VISIT rows or actions.
- Deleted `NewVisitDialog`; stats, Supplier 360, search, PDF/Excel visit paths removed.
- Probe/smoke updated; form-density baseline manifest drops visit-form capture.

## Verification

- Focused unittest: anomaly form, scope chips, appearance v10, visit routing guards, layout constants, event manage actions, stats/pdf/supplier export modules
- `scripts/harness_check.ps1`
- `scripts/smoke_test_v2.py`
