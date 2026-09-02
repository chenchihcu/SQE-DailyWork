# 供應商事件作業佇列精簡（1+2+3）

Plan status: completed

## Goal

Safe-pass 殘件清理、案件佇列 lean COUNT=LIST 查詢、三佇列 lazy 載入與首頁／側欄共用 COUNT；主管檢視移除「僅顯示逾期」。

## Delivered

- Phase 1: `HOME_BACKLOG_*`、export `queue_rows`、manager metrics façade、
  `MANAGER_ACTION_QUEUE_*` → `OPERATIONAL_ACTION_QUEUE_*`、主管檢視 UI 精簡
- Phase 2: `list_overdue_case_queue_rows` / `list_root_cause_pending_case_queue_rows`
  脫離 `list_manager_summary_rows`；RCA COUNT=LIST 測試
- Phase 3: 三佇列 `LazyPageWidget`；`HomeWidget.apply_queue_counts` +
  `_refresh_sidebar_badge` 單次 COUNT

## Verification

- Focused unittest: supplier_event_queues, manager_view_phase6, exports_phase7,
  layout_constants, home_recent_events_panel, list_column_contract,
  surface_usage_structure
- `scripts/harness_check.ps1`
