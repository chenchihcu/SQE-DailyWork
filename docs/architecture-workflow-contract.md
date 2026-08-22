# SQE DailyWork Architecture Workflow Contract

## Purpose

This contract is the design checkpoint for every SQE DailyWork change. The app
is a single ERP-style desktop program with two daily workflow data lines and one
shared master-data area.

## Data Responsibility Matrix

| Area | Tables | Source | Writes Allowed From | Must Not Write |
| --- | --- | --- | --- | --- |
| Shared master data | `suppliers`, `products` | Company product and supplier master data | Manual master-data dialogs; ERP/Excel master import | Supplier events, visit/audit defect notes, warehouse defect records |
| Supplier event management | `visits`, `visit_product_sections`, `visit_defect_notes`, `anomalies`, `anomaly_actions`, `anomaly_analysis_notes`, `anomaly_root_causes`, `corrective_actions`, `effectiveness_verifications`, `anomaly_attachments`, `anomaly_eight_d_reviews`, `anomaly_audit_logs` | Supplier visits, audits, legacy visit defect notes, and confirmed supplier abnormal events | Visit/audit dialogs for visits; explicit conversion for persisted defect notes; anomaly workbench CRUD through `_anomaly_action_service` / `_anomaly_workbench_service` | `defect_records` |
| Warehouse physical nonconforming-product management | `defect_records` | Physical items in the nonconforming-product warehouse | Embedded warehouse tracker only | `visits`, `visit_defect_notes`, `anomalies` (and all anomaly sub-tables) |
| Import audit | `import_batches`, `import_batch_rows` | ERP/Excel import runs | Import services | Workflow data rows |

## Flow Boundaries

0. **Anomaly case-workbench sub-tables** belong exclusively to the supplier-event
   management line. `anomaly_actions`, `anomaly_analysis_notes`,
   `anomaly_root_causes`, `corrective_actions`, `effectiveness_verifications`,
   `anomaly_attachments`, `anomaly_eight_d_reviews`, and `anomaly_audit_logs`
   are read/written only through the service adapters in
   `src/services/event/_anomaly_action_service.py` and
   `src/services/event/_anomaly_workbench_service.py`. They must never be
   written from the warehouse tracker and must never be read for warehouse
   statistics. Timeline is a projection over the authoritative audit log plus
   sub-table rows and must not double count an event that already has an audit
   entry.
   - Status-changing service helpers (`complete_action`, `cancel_action`,
     `record_ca_completion_with_audit`, `record_ca_status_change_with_audit`,
     `record_verification_with_audit`, `create_eight_d_review_with_audit`,
     `append_manual_audit`) bundle the sub-table write with an
     `anomaly_audit_logs` row so the timeline reflects every transition
     without callers re-implementing audit logic. UI dialogs must call these
     helpers instead of the repository directly.

1. `visit_defect_notes` remains a compatible supplier-event store for existing
   visit or audit notes. The current `NewVisitDialog` preserves those notes on
   edit but does not expose a new-note editor or a separate `登錄訪廠缺失` entry.
2. A persisted visit or audit defect becomes a formal supplier abnormal event
   only through an explicit confirmation path that writes `anomalies.visit_id`.
3. Visit or audit defects must never be inserted into `defect_records`.
4. Warehouse nonconforming-product records describe physical inventory items and
   must never become supplier events without a separate, explicit event record.
5. ERP/Excel master imports update only shared master data plus import audit
   rows. They must not create visits, anomalies, visit defect notes, or warehouse
   defect records.
6. Warehouse pending workflow split is data-backed by
   `defect_records.processing_line`, not by labels, hidden UI filters,
   `category`, or `return_slip_type`. Runtime values are `原物料`, `委外加工`, and
   migrated/cleanup-only `未分流`. New and edited rows must save as `原物料` or
   `委外加工`; existing rows default to `未分流` until a user classifies them.
7. `defect_records.supplier_id` is a nullable read-model relationship to the
   shared `suppliers.id`. It is backfilled only by exact supplier-name matches;
   unmatched legacy rows remain NULL. This relationship supports supplier 360
   projections but does not merge warehouse records into supplier-event tables,
   statistics, or exports.
8. Supplier 360 is a read-only aggregation over `anomalies`, `visits`, and
   `defect_records`. Every projected row keeps its source label and source
   identifier. The NCR-to-anomaly action is an explicit user action and records
   `anomalies.source_defect_no` for traceability; it does not mutate or delete
   the originating warehouse record.

## Supplier Anomaly Quality-Report Requirement

- `anomalies.quality_report_required` is the nullable source of truth for
  「品質異常單要求」: `1` means 是, `0` means 否, and `NULL` means a legacy row
  that has not been classified. Schema upgrades add the column without
  backfilling or guessing historical values.
- `NewAnomalyDialog` requires an explicit 是／否 selection before a new or
  edited anomaly can be saved. Read-only preview preserves the stored state.
- `EventListWidget` displays 「品質異常單要求」 for every supplier-event scope:
  anomaly rows show 是／否／未設定 from `quality_report_required`, while pure
  visit rows show 不適用 because they do not own a formal anomaly row.
- Supplier-event Excel detail output is split by the authoritative
  `event_type`: `VISIT` rows go to `訪廠` and `ANOMALY` rows go to `異常`.
  The removed combined sheet `異常事件明細` must not be recreated by filtering
  or relabeling a mixed dataset. The `異常` sheet exports 是／否／未設定 for
  「品質異常單要求」 and keeps raw 「異常類別」 separate from 「原因分類」;
  the visit sheet omits anomaly-only fields. This split supports downstream
  filtering without changing existing charts, summary totals, supplier
  ranking, or warehouse NCR reports.

## Supplier Anomaly SMT Process Keywords

- `anomalies.process_keywords` stores optional multi-value SMT process keywords as
  newline-delimited text. It is independent from `anomalies.category` and must not
  be merged into warehouse NCR data or the category Pareto.
- `NewAnomalyDialog` exposes keyword entry through `TagInputWidget`; users may pick
  presets from `ui_settings.smt.process_keywords.v1` or enter custom keywords.
- Keyword statistics use `get_anomaly_process_keyword_pareto_by_range` as the single
  implementation for the stats page chart and Excel export sheet/chart PNG.

## Supplier Anomaly ERP Trace Numbers

- `anomalies.anomaly_source` is one of six persisted values:
  `原物料進貨（IQC）`、`廠內製令`、`委外加工`、`委外進貨`、`訪廠／稽核`、`其他`.
- Trace-number columns on `anomalies` are:
  `material_receipt_no`、`internal_work_order_no`、`outsource_work_order`,
  `outsource_receipt_no`. There is no purchase-order column.
- `NewAnomalyDialog` shows trace fields conditionally by `anomaly_source`.
  `訪廠／稽核` shows none; `其他` shows all four as optional.
- ERP format rules live in appearance preferences v9
  (`erp_*_pattern` fields). Non-empty trace numbers must match the configured
  regex. Multiple anomalies for the same supplier may share the same trace
  number; `anomaly_no` remains the unique case identifier.
- NCR `轉開供應商異常` may copy `work_order_no` and `internal_work_order_no`
  into the anomaly form plus `source_defect_no`. `transfer_slip_no` is not
  equivalent to `outsource_receipt_no` and must not be auto-mapped.

## Supplier Anomaly Working Folders

- Every successfully created `anomalies` row gets a working folder under
  `Outputs/ncr number file/` named `<供應商名稱><異常單號>`.
- The same rule applies to standalone anomalies, anomalies linked or
  synchronized to a visit, and legacy visit defect notes explicitly confirmed
  as formal supplier anomalies. Creating a visit or a lightweight visit defect
  note alone does not create this folder.
- Folder creation is idempotent. Windows-invalid filename characters in the
  supplier-name component are replaced with `_`; the stored supplier name and
  anomaly number are never changed.
- Each folder contains a same-stem `.md` file whose body is deterministic YAML.
  All user-facing keys use Traditional Chinese. The canonical field order is owned by
  `src/services/event/_anomaly_markdown.py`; absent scalar values remain as
  empty strings and `attachments` remains an explicit list. Attachment entries
  contain both filename and caption.
- The service layer overwrites the YAML snapshot after create, edit, visit-link
  update, close, closure-date adjustment, reopen, and attachment mutations.
  SQLite and the attachment store remain authoritative; the Markdown file is a
  synchronized operational snapshot, not a second writable data source.

## UI Entrypoint And Folder Boundaries

- The app has one daily desktop shell: `main.py` with `src/ui/main_window.py`.
- The sidebar grouping expresses workflow structure, not data ownership: four
  domain group headers (text labels) — 供應商事件, 倉庫不合格品, 供應商管理, 系統 — organize
  首頁 plus supplier-event create/query/statistics pages; 倉庫不合格品 holds 建立不合格品 /
  待處理委外加工 / 待處理原物料 / 歷史紀錄 / 不合格品統計分析; 供應商管理 holds 供應商總覽 / 基礎資料;
  系統 holds 顯示設定. The four supplier-event scopes (單獨異常 / 訪廠發現異常 /
  訪廠紀錄 / 已結案) are page-local scope chips on the single 事件管理 page, not
  first-class sidebar rows.
- The sidebar emits `nav_activated(action)` (`("page", PAGE_KEY)` or
  `("scope", EVENT_SCOPE_*)`); `MainWindow._PAGE_KEY_TO_INDEX` maps PAGE_KEY to the
  stack index, so the sidebar stays decoupled from stack indexes.
- Sidebar page indexes and stack routing are `0 首頁 / 1 事件管理 / 2 異常事件統計
  / 3 建立不合格品 / 4 待處理委外加工 / 5 待處理原物料 / 6 歷史紀錄 /
  7 不合格品統計分析 / 8 基礎資料` (NCR offset 3). When indexes change, update the
  index constants, legacy aliases (`ANOMALY/VISIT/CLOSED_PAGE_INDEX`),
  `ncr.embed.NCR_PAGE_OFFSET`, and the affected tests in the same change.
- Warehouse nonconforming-product tracking stays under the embedded `src/ncr/`
  workflow and exposes create, two formal pending processing-line pages, and
  history as first-class shell pages. The old generic pending route may only be
  retained as compatibility alias and must not be used by new navigation.
- Supplier and warehouse sidebar badges are read-only status indicators. They
  must not create cross-line writes or merge supplier-event and warehouse
  statistics.
- Warehouse pending badges count exactly `status <> '已結案' AND processing_line =
  <formal line>`. `未分流` records are surfaced as cleanup/to-do warnings, not
  merged into either formal badge or treated as a guessed line.
- Runtime data, generated reports, and visual/debug artifacts stay in `data/`,
  `Outputs/`, `scratch/`, or the ignored root runtime `ncr/data/`; durable
  project guidance belongs in `docs/`. Writable roots resolve through
  `src/app_paths.py` (repository root in source runs; executable directory in
  frozen PyInstaller onedir builds).
- New source folders require a clear owner that is not already covered by
  `src/ui/`, `src/services/`, `src/database/`, `src/ncr/`, `scripts/`, or `tests/`.

## Statistics Boundary

- Supplier event statistics query supplier-event tables and must be labeled as
  supplier-event analysis.
- Supplier anomaly closure statistics use `anomalies.closed_at` as the
  user-selected closure date; charts, lists, exports, and monthly cache refresh
  must stay aligned to that single source of truth.
- Warehouse nonconforming-product statistics query `defect_records` and must be
  labeled as warehouse physical nonconforming-product analysis.
- A combined quality metric is allowed only when the UI explicitly separates the
  two sources in the same view.

## Anomaly Workbench Read Model Parity

- `repository.get_anomaly_overview_card` is the single source of truth for the
  workbench summary (current next action, overdue flag, open action count, root
  cause status, corrective action status, effectiveness verification result,
  analysis notes flag, attachment count). The UI dialog, the event list, the
  Excel detail sheet, the PDF payload, and the Markdown snapshot must all
  consume this read model — UI / exporters must not recompute their own join.
- `_query_service.list_events` and `_query_service.list_events_by_range`
  annotate each anomaly row with the overview card fields so every consumer
  (table, dashboard cards, export) sees the same numbers.
- Excel 異常 detail sheet appends the parity columns (`逾期`, `目前處置`,
  `進行中處置數`, `根本原因狀態`, `改善措施狀態`, `有效性驗證`, `附件數`)
  after the existing legacy fields. Removing any of the legacy columns is a
  contract change and must follow the standard change checklist.
- VISIT rows are intentionally not enriched; only ANOMALY rows own the workbench
  sub-tables and the parity rules.

## Change Checklist

Before each change, classify the impact:

- shared master data
- supplier event management
- warehouse physical nonconforming-product management
- import/audit trail
- statistics/reporting
- UI entrypoint or layout
- folder/documentation ownership

After each change, verify:

- no cross-line writes were introduced
- visible copy names the correct workflow source
- workflow splits define their data source, route/page key, badge/count query,
  legacy-data handling, tests, and docs; label-only or hidden-filter splits are
  not sufficient
- folder placement matches the owning workflow or documentation index
- focused tests cover the affected boundary
- `scripts/verify.ps1` passes for source, script, UI, data-boundary, and
  governance changes

## Transaction, Migration, And Reporting Boundaries

- `SQE_DB_PATH` is resolved only by `src/database/connection.py`; main, embedded
  NCR, tests, reports, and probes must consume that connection boundary rather
  than defining their own formal database path.
- Anomaly mutation plus monthly-cache refresh is one SQLite transaction. Derived
  Markdown/folder snapshots run after commit and return non-destructive warnings;
  they must never make the UI imply that the authoritative row was not saved.
- Legacy migration is all-or-nothing. A row error rolls back imported business
  rows, leaves completion metadata absent, and emits reconciliation evidence.
- Repository validation owns anomaly-number format/date-prefix/uniqueness and
  anomaly/visit supplier consistency. UI validation is feedback, not the data
  integrity boundary.
- Product import identity is `(supplier, product_code)`. Only a truly unassigned
  product may be adopted by a new supplier; stage mismatch blocks apply and uses
  the existing stage-change process.
- Excel labels keep anomaly-date cohort state separate from `closed_at` period
  activity. Chart renderer failures preserve workbook data but surface
  `完成但有警告` with the exact missing-chart list.
## Global Display And System Preferences

- `ui_settings` is the local, application-wide display and system preference container.
  The shell writes only `appearance.preferences.v5`, a strict JSON payload with 27 typed fields across 5 domain tabs:
  1. **外觀主題 (Appearance & Theme)**: `density` (`compact` / `standard` / `comfortable`), `sidebar_density` (`compact` / `standard`), `accent_color` (`electric_blue` / `slate_navy` / `emerald` / `amber`), `text_scale` (`standard` / `large`), and `contrast_mode` (`standard` / `high`).
  2. **視覺表格與互動 (Visual, Tables & Interaction)**: `table_density` (`compact` / `standard` / `comfortable`), `alternating_row_colors` (`bool`), `table_grid_lines` (`bool`), `table_page_limit` (`25` / `50` / `100` / `0`), `enable_animations` (`bool`), `table_double_click_action` (`menu` / `preview` / `edit`), `search_mode` (`live` / `manual`), `stats_default_span_months` (`3` / `6` / `12`), and `pareto_show_cutoff_line` (`bool`).
  3. **表單業務預設 (Form & Business Defaults)**: `default_responsible_person` (`str`), `default_anomaly_category` (`str`), `default_sync_visit` (`bool`), `default_due_days` (`7` / `14` / `30`), and `default_visit_time_slot` (`上午` / `下午` / `全天`).
  4. **匯出與報告 (Export & Reports)**: `default_export_dir` (`str`), `export_completion_action` (`open_file` / `open_folder` / `notify_only`), `report_organization_header` (`str`), and `export_include_charts` (`bool`).
  5. **系統與備份 (System & Backup)**: `default_startup_page` (`home` / `events` / `defects` / `stats`), `auto_backup_prompt` (`bool`), `backup_retention_count` (`5` / `10` / `20` / `30`), and `confirm_on_delete` (`bool`).
- Valid legacy `appearance.preferences.v1`, `v2`, `v3`, and `v4` payloads map in memory to v5 defaults for newly added fields; missing, malformed, unknown-key, or unknown-value payloads resolve to the default profile without rewriting stored data.
- This preference never changes core event, warehouse, statistics, export, or navigation data. Existing NCR keys, including `defect_list_columns`, remain compatibility-owned by the NCR module.

## Startup Performance And Lazy Loading Boundaries

- Heavy third-party libraries (`openpyxl`, `reportlab`, `matplotlib`) must never be imported statically at module root in services or UI classes loaded during startup. Always import them inside the specific function or method where they are invoked.
- Module-level style instantiation is prohibited; style objects (e.g. `Font()`, `PatternFill()`, `Border()`) must be encapsulated in cached helper functions (e.g. in `src/ui/export_helpers.py`).
- Container pages wrapping full forms (such as `EventCreatePage` and `LazyPageWidget`) must support lazy initialization (`lazy_load=True`) and defer child form creation to `_ensure_form_installed()` on first `showEvent`.
- Avoid redundant `refresh_data()` queries during `MainWindow._setup_ui` when child widgets already load initial data in `__init__`.
- In UI files, maintain service module imports (e.g. `from ncr.services import export_service`) at module level while keeping the service file itself lazy-loading external heavy dependencies. This guarantees `unittest.mock.patch` stability in tests while eliminating startup latency.

