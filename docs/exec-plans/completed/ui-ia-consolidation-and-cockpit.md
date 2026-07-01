# UI IA Consolidation + Daily Cockpit

Date: 2026-06-07
Completed: 2026-06-25

> **Completion note**: The consolidation was implemented, but the final sidebar settled
> at **6 items** (not 5 as planned) because an `不合格品統計分析` group was added after
> the plan was written. The `NCR_PAGE_OFFSET` landed at **3** (not 4 as planned).
> These divergences are reflected in the current `README.md` and
> `docs/architecture-workflow-contract.md`. The plan's core goals (event-entry
> consolidation, home cockpit backlog, scope-tab routing, dead-code removal) were achieved.

## Context

The home page sat ~70% empty (six small KPI cards, then blank), the sidebar had
seven items where three of them (`異常一覽表 / 訪廠紀錄一覽表 / 異常已結案查詢`)
were the same `EventListWidget` with a different `fixed_scope`, and the
`EventListWidget` scope-tab path was dead code. There was also an orphan
`visit_anomaly_widget` (never inserted into the stack) and a routing bug where the
首頁「訪廠發現異常」KPI dropped its scope on a fixed-scope page. User approved
revising the UI/IA contracts. Scope: P0 = A (event-entry consolidation) +
B2 (home daily cockpit) + H (dead-code/routing cleanup). Out of scope: sidebar
recolor, page-header rework, list interaction model, master toolbar, statistics
token cleanup.

## Contract

- One `事件管理` page (index 1) holds all supplier-event views as scope tabs:
  `單獨異常 / 訪廠發現異常 / 訪廠紀錄 / 已結案` (default 單獨異常; 已結案 tab locks
  the status filter to 已結案).
- Page indexes: `0 首頁 / 1 事件管理 / 2 異常事件統計 / 3 基礎資料 / 4 不合格品追蹤`
  (NCR offset 4). Legacy index aliases (`ANOMALY/VISIT/CLOSED_PAGE_INDEX`) kept.
- Home = six KPI cards + one read-only backlog (待辦) list. The backlog list reads
  existing services only and routes through existing navigation; no new write
  paths, tables, caches, or migrations.
- Data boundaries unchanged: supplier-event vs warehouse statistics stay
  separated; warehouse stays a single embedded page.

## Scope of change

- `src/ncr/embed.py`: `NCR_PAGE_OFFSET` 6 → 4.
- `src/ui/widgets/defect_list_widget.py`: `EVENT_QUERY_SCOPE_TABS` reordered +
  `已結案` tab added; default scope `ANOMALY_ONLY`; status combo locks/disables on
  the 已結案 tab and restores otherwise.
- `src/ui/sidebar_nav.py`: nav consolidated to five items.
- `src/ui/main_window.py`: index constants + aliases; single `events_widget`
  replaces the three fixed-scope widgets; `open_event_query_with_filters` routes
  every scope through the one page (fixes 訪廠發現異常); `refresh_all_views` and
  badge wiring simplified; orphan widget removed.
- `src/ui/widgets/home_widget.py`: read-only `HomeBacklogPanel` (table of
  open/overdue anomalies, overdue first) + warehouse pending shortcut.
- Contracts/docs: `docs/ui-layout-theme-contract.md`,
  `docs/architecture-workflow-contract.md`, `README.md`.
- Tests: `test_top_nav_compact_height`, `test_home_recent_events_panel`,
  `test_ncr_embedding_smoke`, `test_ux_event_query_and_master_nav` updated.

## Non-goals

- No change to event/visit/anomaly/warehouse data contracts or services.
- No new statistics, write paths, or schema migrations.
- Sidebar recolor, page-header rework, list interaction, master toolbar, and
  statistics token cleanup are deferred (C/D/E/F/G).

## Verification

- Offscreen focused tests for sidebar/IA, NCR embedding, event query, home.
- `scripts/verify.ps1` + `scripts/harness_check.ps1`.
- Native `scripts/qt_visual_probe.py --target main` (read PNG): six KPI cards +
  backlog list fill the first screen; sidebar shows five items.
- Manual: scope tab switching incl. 已結案 status lock; 訪廠發現異常 KPI scope;
  backlog row + warehouse shortcut routing; 基礎資料 return to event page.
