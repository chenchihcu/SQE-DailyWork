# Changelog

All notable changes to **SQE DailyWork** are documented here.
The version is the single source of truth in `src/app_version.py` (`__version__`)
and is shown in the main-window title bar and the startup log (`logs/app.log`).

Format follows [Keep a Changelog](https://keepachangelog.com/); this project
uses semantic versioning (MAJOR.MINOR.PATCH).

## [Unreleased]

### Added
- Consolidated supplier-event **作業佇列** page (`SupplierEventOpsPage`) with chips
  for 逾期案件 / 根因待查 / 處置項目 / 案件總覽; legacy PAGE_KEY aliases preserved.
- Master data split into four fixed-scope sidebar pages (原物料供應商 / 委外加工 /
  原物料 / 半成品/成品) with `suppliers.category` migration and `products.item_category`.
- User-maintainable anomaly category and source lexicons (`ui_settings`
  `supplier_event.anomaly_categories.v1` / `supplier_event.anomaly_sources.v1`)
  managed from **顯示設定 → 表單與業務**.

### Changed
- Sidebar supplier-event navigation reduced to four items (新增異常 / 事件查詢 /
  作業佇列 / 異常事件統計); operational queue counts moved from sidebar badges to
  ops-page chips.
- Event query toolbar deduped (removed redundant 新增異常, source tag, status 已結案
  combo, overdue lens); workbench overview deduped.
- Statistics dashboards use visible `AnalyticsWorkflowShell` control rows.

### Removed
- Retired visit product UI (`NewVisitDialog`, visit create/edit/preview dialogs,
  visit event scopes, visit statistics/export paths); legacy `visits` schema remains
  for existing data only.
- Retired `VisitDetailDialog`, `AddCorrectiveActionDialog`, and
  `CompleteCorrectiveActionDialog` from product UI paths.

### Historical (superseded 2026-08-31 by 作業佇列 consolidation above)

The entries below document intermediate IA steps before the consolidated
`SupplierEventOpsPage`; they are **not** the current product navigation.

#### Added (intermediate)
- Supplier-event operational queues in the sidebar (`逾期案件` / `根因待查` /
  `處置項目`) with shared COUNT SSOT and `SupplierEventQueuePage`.

#### Changed (intermediate)
- Default startup page is `events` (事件查詢); legacy `home` preference migrates to
  `events` on load.
- Sidebar supplier-event navigation labels aligned to definition axes: `事件查詢`,
  `逾期案件`, `根因待查`, `處置項目`, `案件總覽` (PAGE_KEY unchanged). Overview export
  field `進行中處置數` renamed to `處置項目數` (`open_action_count` key unchanged).
- Sidebar is the sole navigation surface; the home hub page and sidebar `首頁` row
  are removed. Stack index `0` remains a retired ghost placeholder (NCR offsets
  unchanged).
- Manager view keeps only the case summary table; the operational action tab and
  duplicate metric strip are removed. Manager Excel exports a single `案件總覽` sheet.
- Manager view drops the redundant「僅顯示逾期」filter; overdue work uses the
  `逾期案件` operational queue instead.
- Case queue lists use COUNT-aligned lean queries instead of the manager summary
  read model; queue pages lazy-load on first navigation; sidebar badges consume
  one shared queue COUNT refresh.
- `CASE_QUEUE_COLUMNS` / `CASE_QUEUE_RCA_COLUMNS` replace `HOME_BACKLOG_COLUMNS`;
  operational action queue owner label is `處置負責人`.
- Retired `HOME_BACKLOG_*` layout constants and manager-view export `queue_rows`
  compatibility parameter.
- Removed dedicated visit-create UI: sidebar 「新增訪廠」, event-list toolbar
  button, Supplier 360 「安排訪廠」, and `EventCreatePage` visit branch. Product
  anomaly create always uses `sync_visit=False` and no longer INSERT `visits`.
  *(Superseded 2026-09-02: visit product UI fully retired; see Removed above.)*
- Removed orphan `tests/visual_baseline/home/` baselines and dead `HomeWidget` code;
  `harness_check.ps1` now fails on visual baseline directories not listed in
  `qt_probe_targets.json`.

## [1.2.0] - 2026-08-27

Case workbench Phase 7: export/report parity with overview SSOT, manager-view Excel,
supplier repeat summary, weekly PPTX overdue alignment, and unsigned Windows onedir release.

### Added
- Hypothesis tree PNG renderer for Excel range reports and event PDF exports.
- Manager view Excel export (`案件總覽` + `作業清單`) with UI `匯出 Excel` action.
- Excel anomaly detail append columns: `原因假設數`, `已採納假設`, `重複警示`.
- Markdown anomaly snapshots append overview / hypothesis / open-action blocks.
- Supplier quarterly report: `重複警示` summary and overview quality columns on anomalies.
- Weekly PPTX overdue KPI and row highlighting via `get_anomaly_overview_card()` SSOT.
- `scripts/verify_exports_phase7.ps1` focused gate and `tests/test_exports_phase7.py`.

### Changed
- Event PDF exports include quality-conclusion and open-action sections from overview SSOT.
- Statistics Excel respects `export_include_charts` for chart and hypothesis PNG embedding.

### Fixed
- Phase 8 pre-release audit: overview `repeat_link_count` SSOT, case-action overdue
  unification, range-export trace columns, hypothesis reparent level cascade,
  UI action/verification gating, dirty-guard on dialog cancel, manager-view
  native visual probe target, `product_records` VIEW `is_active` filter with
  formal Promotion CLI, and coverage baseline recalibration (72.3% / fail-under 71.0%).
- Reopen anomaly refreshes monthly stats cache when the service defers commit.
- Supplier 360 repeat-flag count no longer crashes when repeat-links schema is absent.

## [1.1.0] - 2026-08-22

Operational release with supplier-oriented UI closeout, frozen path contract, and
Windows onedir packaging.

### Added
- Supplier-oriented workbench: scope chips, Ctrl+K global search, supplier 360,
  case stepper, quarterly supplier report export, and NCR `supplier_id` linkage.
- `src/app_paths.py` as the single source for writable runtime roots in source
  and PyInstaller frozen builds.
- Windows distribution tooling: `scripts/sqe_dailywork.spec` and
  `scripts/build_windows.ps1` (onedir + portable zip).
- `main.py --smoke-exit` for automated frozen-bundle smoke checks.

### Fixed
- NCR create embedding smoke test aligned with `NcrCreateFormContent` wrapper DOM.
- `scripts/smoke_test_v2.py` aligned with strict supplier product scoping and
  anomaly trace-source requirements.

### Changed
- Version marker bumped to `1.1.0` in the window title and startup log.

## [1.0.0] - 2026-07-04

First production release of the single-user local PySide6 + SQLite Supplier
Quality Engineering desktop tool.

### Added
- Application version marker: `src/app_version.py` (`__version__ = "1.0.0"`),
  surfaced in the window title (`SQE DailyWork v1.0.0 - SQE 工作台`) and logged
  at startup so a build is identifiable from a bug report / log file.

### Fixed
- Audit timestamps (`created_at` / `updated_at`) now use local wall-clock time
  instead of UTC, so they no longer show the previous day for UTC+8 users near
  midnight. Date-range statistics are unaffected (they key off the date-only
  `anomaly_date` / `closed_at` values).
- `SQE_DB_PATH` override now also aligns the derived data directory and legacy
  database path, so the override's parent directory is created correctly on
  first run.

### Housekeeping
- Removed dead Genspark integration files and stopped tracking development/session artifacts
  (`.omo/`, `artifacts/visual/*.png`, root probe screenshots, diff dumps) from
  version control.
