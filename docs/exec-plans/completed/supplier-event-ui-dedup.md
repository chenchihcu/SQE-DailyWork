# Supplier Event UI Dedup

Plan status: completed

## Goal

Consolidate supplier-event operational lists (逾期案件 / 根因待查 / 處置項目 / 案件總覽) into a single **作業佇列** page with chips; remove redundant event-query controls, workbench duplicates, orphan preferences, and unused corrective dialogs. No schema or `NCR_PAGE_OFFSET` changes.

## Decisions (locked)

- New nav key: `PAGE_EVENT_OPS`. Legacy keys (`PAGE_EVENT_OVERDUE`, `PAGE_EVENT_ROOT_CAUSE`, `PAGE_EVENT_OPEN_ACTIONS`, `PAGE_MANAGER_VIEW`) are compatibility aliases mapping to the same stack index and forcing the matching chip.
- Stack: `EVENT_OPS_PAGE_INDEX = SUPPLIER_360_PAGE_INDEX + 1`. All four legacy `*_PAGE_INDEX` constants alias to it. `_PAGE_INDEX_TO_KEY` maps only `PAGE_EVENT_OPS`.
- Chip counts: overdue / root-cause / open-actions chips use `get_supplier_event_queue_counts()`; 案件總覽 chip has no count. Sidebar badge disabled for 作業佇列.
- Header: title fixed `作業佇列`; subtitle follows active chip via `sync_header()` after `_switch_primary_page`.
- Embedded inner pages: `margins=0`; queue banner `QueryWorkflowShell` removed entirely when embedded.
- Workbench return: ops-family `source_page_key` → `返回作業佇列` + `open_supplier_event_ops(source_key)`.
- Event query: remove toolbar 新增異常, status 已結案 combo item, source tag, overdue lens (`overdue_only` UI path only; repository param kept for tests).
- Visit rows: preview via `NewVisitDialog(read_only=True)` only; delete `VisitDetailDialog`.
- Preferences: remove overdue UI controls; retain JSON fields via retained fields pattern.
- Statistics: visible `AnalyticsWorkflowShell` hosts control row (no `hide()`).

## Progress

- [x] Exec plan
- [x] Ops page + routing
- [x] Event list dedup
- [x] Visit menu + workbench
- [x] Preferences + stats shell
- [x] Delete unused corrective dialogs
- [x] Docs / tests (focused unittest); native visual baselines pending manual refresh

## Verification

- Focused unittest modules listed in plan (top nav, supplier queues, event list, workbench, appearance, surface usage).
- `scripts/harness_check.ps1`
- Native `qt_visual_probe.py --target main|event-list|manager-view|workbench|appearance-settings|dialog-density` (one target per run).
