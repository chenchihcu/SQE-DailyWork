# Phase 8 正式發布前全面稽核修正

Plan status: completed — pre-release audit remediation verified 2026-08-28

## Scope

- Pre-release audit of uncommitted Phase 1–7 rollout + stable-module hygiene sweep.
- Fix P1 contract violations before release; batch P2/P3 cleanup; full verification gates.

## P1 remediation map

| # | finding | status |
| --- | --- | --- |
| 1 | `get_anomaly_overview_card()` missing `repeat_link_count` | **done** |
| 2 | Overdue dual semantics (`anomalies.due_date` vs case-action SSOT) | **done** |
| 3 | `list_events_by_range` missing ERP trace columns | **done** |
| 4 | Hypothesis reparent without subtree `level` cascade | **done** |
| 5 | Hypothesis non-status updates missing audit log | **done** |
| 6 | Verification button not gated by `verification_status` | **done** |
| 7 | Closed-case action buttons not disabled | **done** |
| 8 | `RepeatIssuesPanel` missing `RuntimeError` guard | **done** |
| 9 | Dirty-guard bypass on Cancel/reject | **done** |
| 10 | Phase 3 exec-plan internal contradiction | **done** (moved to `completed/`) |
| 11 | Missing contract-critical regression tests | **done** |

## P2 cleanup

- `format_current_action_text()` SSOT; Excel import + path name helpers; layout_constants;
  `disposable_runtime_enabled()`; query failure logging.

## Verification evidence

- Focused: `test_anomaly_overview_parity`, `test_hypothesis_phase3`, `test_anomaly_management_page`,
  `test_exports_phase7` (12-PNG), `test_manager_view_phase6` (NCR boundary),
  `test_repeat_issue_phase5` (warehouse boundary), `test_monthly_stats_expansion`,
  `test_product_records_view_write_path` (inactive hidden from VIEW)
- Native visual: `manager-view` baselines @ 1.0/1.25/1.5; workbench/dialog-density/supplier-360 regress PASS
- Sequential Full + Soak: `scratch/verify-full-chunked-final.log`, `scratch/verify-soak-final.log` PASS
- Coverage baseline recalibrated 2026-08-28 (`docs/release/coverage-baseline.json` line 72.3% / fail-under 71.0%); gate PASS via `assert_coverage_baseline.py`
- `product_records` VIEW `is_active` filter: formal Promotion verified; backup `data/sqe_v2_backup_product_records_view_is_active_v1_20260828_204019.db`; audit `scratch/product-records-view-audit-post.json`
- Qt SEH hygiene: `test_anomaly_management_page.tearDown` closes `topLevelWidgets()`; chunked unittest runner in `verify.ps1`
- Button audit: subprocess-per-page isolation; `event_create_anomaly` structural-only; UTF-8 worker stdout for cp950
- `scripts/harness_check.ps1` (after manifest + exec-plan sync)

## Residual (accepted)

- Risk ledger Active: visit display, supplier/product VERIFY, Phase0 raw hash
- Authenticode signing deferred
