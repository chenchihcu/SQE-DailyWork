# Production Hardening — P0/P1/P2 Complete

## Goal
Hardening SQE DailyWork before production go-live: fix bugs, close workflow gaps, add fool-proofing.

## Completed Items

### P0 — Blocks production
- **Phase 1.1**: `close_anomaly()` validates `improvement_desc` is non-empty (service layer)

### P1 — High risk
- **Phase 1.4**: Single-instance lock via `QSharedMemory` in `main.py`
- **Phase 1.5**: `smoke_test_v2.py` defaults to scratch DB; `--danger-use-prod-db` flag for intentional prod runs
- **Phase 1.6**: Dead code fix — `_update_outsource_row_visibility` now compares `stage == "委外"` directly
- **Phase 1.7**: Global exception handler (`sys.excepthook`) + Qt message handler + file+stream logging to `logs/app.log`
- **Phase 1.8**: `isinstance(data, list)` guard in `_on_chart_bar_hovered` before calling `_on_supplier_bar_hovered`
- **Phase 2.1**: `delete_visit` unlinks anomalies (`SET NULL`) instead of blocking
- **Phase 2.2**: Added `idx_defect_records_status` and `idx_defect_records_event_date` indexes
- **Phase 2.3**: Removed AI-tool hex paths from `scripts/verify.ps1`
- **Phase 2.4**: Removed `shell=True` fallback from LINE service launch
- **Phase 2.5**: Confirmed English service-layer errors + `popup_i18n.py` translation pattern intact
- **Phase 2.6**: `.env` loading (`SQE_DB_PATH`, `SQE_LOG_LEVEL`), high-DPI support, `xhtml2pdf`+`Pillow` in requirements

### P2 — Quality of life
- **Phase 2.7**: Unsaved-changes guard on all three dialog close events (`NewAnomalyDialog`, `NewVisitDialog`, `CloseAnomalyDialog`). Prompts "有未儲存的變更，確定要放棄嗎？" with 放棄/取消 buttons when user closes a dirty form.
- **Phase 2.8**: Tab-switch dirty guard — N/A (`MasterDataWidget` has no in-place editing; all changes go through modal dialogs)
- **Phase 2.9**: Standardized delete confirmation across all widgets to use custom "刪除"/"取消" buttons (replacing inconsistent `QMessageBox.question` Yes/No pattern)

### Skipped / Deferred
- **Phase 1.2** (CASCADE DELETE on FKs) — Deferred: too risky without table rebuild migration; existing manual delete checks guard against orphans
- **Phase 1.3** (synchronize FKs) — Not needed; existing schema works correctly

## Verification

| Gate | Result |
|------|--------|
| `compileall` | No errors |
| Unit tests (non-Qt) | 57/57 pass |
| Smoke test (scratch DB) | Pass |
| Unittest discover (excl. Qt tests) | All pass |

## Key Files Changed
- `main.py` — Single-instance, logging, exception hooks, .env, high-DPI
- `src/database/repository.py` — delete_visit SET NULL, indexes, category column
- `src/services/event_service.py` — close_anomaly validation
- `scripts/smoke_test_v2.py` — Scratch DB default
- `scripts/verify.ps1` — AI-tool paths removed
- `src/services/line_service.py` — shell=True removed
- `src/ui/widgets/defect_form_widget.py` — Outsource dead code, closeEvent dirty guard (all 3 dialogs)
- `src/ui/widgets/master_data_widget.py` — Standardized delete confirmations
- `src/ui/widgets/event_actions.py` — Already had correct delete pattern
- `src/ui/widgets/stats_view_widget.py` — Chart hover type guard
- `tests/test_master_import_service.py` — Updated for supplier-scoped product lookup
- `requirements.txt` — xhtml2pdf, Pillow
