# SQE DailyWork Architecture Workflow Contract

## Purpose

This contract is the design checkpoint for every SQE DailyWork change. The app
is a single ERP-style desktop program with two daily workflow data lines and one
shared master-data area.

## Data Responsibility Matrix

| Area | Tables | Source | Writes Allowed From | Must Not Write |
| --- | --- | --- | --- | --- |
| Shared master data | `suppliers`, `products` | Company product and supplier master data | Manual master-data dialogs; ERP/Excel master import | Supplier events, visit/audit defect notes, warehouse defect records |
| Supplier event management | `visits`, `visit_product_sections`, `visit_defect_notes`, `anomalies`, `case_actions`, `action_verifications`, `case_action_legacy_map`, `anomaly_analysis_notes`, `anomaly_root_causes`, `anomaly_hypotheses`, `anomaly_attachments`, `anomaly_eight_d_reviews`, `anomaly_audit_logs`; legacy rollback snapshots: `anomaly_actions`, `corrective_actions`, `effectiveness_verifications` | Legacy supplier visits, audits, visit defect notes, and confirmed supplier abnormal events; visit product UI is retired | `NewAnomalyDialog` / `EventCreatePage`; `AnomalyManagementPage` workbench; Action writes through `_case_action_service`; remaining workbench CRUD through `_anomaly_workbench_service`; repository visit CRUD is test/script opt-in only | `defect_records`; post-migration writes to legacy Action tables; product visit dialogs or visit INSERT |
| Warehouse physical nonconforming-product management | `defect_records` | Physical items in the nonconforming-product warehouse | Embedded warehouse tracker only | `visits`, `visit_defect_notes`, `anomalies` (and all anomaly sub-tables) |
| Import audit | `import_batches`, `import_batch_rows` | ERP/Excel import runs | Import services | Workflow data rows |

## Flow Boundaries

0. **Anomaly case-workbench sub-tables** belong exclusively to the supplier-event
   management line. `case_actions`, `action_verifications`,
   `case_action_legacy_map`, `anomaly_analysis_notes`, `anomaly_root_causes`,
   `anomaly_attachments`, `anomaly_eight_d_reviews`, and `anomaly_audit_logs`
   are read/written only through the service adapters in
   `src/services/event/_case_action_service.py` and
   `src/services/event/_anomaly_workbench_service.py`. They must never be
   written from the warehouse tracker and must never be read for warehouse
   statistics. Timeline is a projection over the authoritative audit log plus
   sub-table rows and must not double count an event that already has an audit
   entry.
   - **Evidence chain (Phase 3 contract):** investigation evidence flows
     analysis note → optional attachment (`related_note_id`) → optional
     multi-layer hypothesis (`anomaly_hypotheses`) → optional
     attachment (`related_hypothesis_id`) → 1:1 root cause conclusion.
     Consumers (overview, timeline, Markdown, export) must use a single
     read-model helper (`list_anomaly_evidence_chain`, planned) rather than
     ad-hoc per-table joins. See
     `docs/exec-plans/completed/2026-08-26-phase3-items-20-23-hypothesis-contract.md`.
   - **Workbench header closure (Phase 4):** `AnomalyManagementPage` and
     `CloseAnomalyDialog` / `ReopenAnomalyDialog` are the primary close/reopen
     surfaces. Close attachments use `EvidenceAttachmentPanel` metadata writes.
     Reopen requires a non-empty reason stored in `anomaly_audit_logs` as
     `CASE_REOPENED`; closure fields on `anomalies` are cleared. See
     `docs/exec-plans/completed/2026-08-26-phase4-items-01-24-workbench-ui.md`.
   - `case_actions.action_type` is one of `NEXT_ACTION`, `CONTAINMENT`,
     `CORRECTION`, `CORRECTIVE_ACTION`, or `SYSTEMIC_IMPROVEMENT`; execution
     status is one of `已規劃`, `執行中`, `已完成`, or `已取消`.
   - Verification status is derived, not stored on `case_actions`. Only completed
     `CORRECTIVE_ACTION` and `SYSTEMIC_IMPROVEMENT` rows with
     `verification_required = 1` accept append-only `action_verifications`.
     The latest verification produces `待驗證 / 有效 / 無效 / 無法判定`;
     non-improvement types are `不適用`, and explicitly waived improvement
     actions are `不需要`.
   - Status-changing Action helpers (`create_case_action`, `update_case_action`,
     `start_case_action`, `complete_case_action`, `cancel_case_action`, and
     `record_action_verification`) bundle the sub-table write with an
     `anomaly_audit_logs` row so the timeline reflects every transition
     without callers re-implementing audit logic. UI dialogs must call these
     helpers instead of the repository directly.
   - `get_anomaly_overview_card()` is the read-model SSOT for current Action,
     due date, overdue, execution status, and verification status. Overdue means
     an open anomaly has at least one `已規劃 / 執行中` Action whose non-empty
     due date is earlier than today; completed and cancelled rows never count.
   - Legacy `anomaly_actions`, `corrective_actions`, and
     `effectiveness_verifications` remain rollback snapshots. The deterministic
   `case_actions_v1` migration records lineage in `case_action_legacy_map`,
   remaps colliding corrective IDs with a fixed UUIDv5 namespace, and installs
   guards that reject new-version `INSERT` and `UPDATE` statements on the old
   Action tables. They are not dropped by this rollout.
  - `anomaly_attachments` is the SQLite metadata SSOT for the Phase 2
    attachment foundation. `related_ca_id` is retained only for legacy
    lineage; new links use `related_action_id` and optional `related_note_id`.
    `file_type` and `uploaded_by` are system metadata, and category values are
    the nine design-framework categories with legacy Traditional-Chinese
    labels preserved on read.
  - Physical bytes remain under
    `data/attachments/anomaly/{anomaly_id}/`, resolved from the active
    `SQE_DB_PATH` data directory. `captions.json` and image-only attachment
    APIs remain a legacy compatibility surface. The workbench read projection
    marks DB rows as `storage_state=present/missing` and exposes unregistered
    physical files as `legacy_physical=true` without guessing their category,
    note, Action, or uploader. Item-level Phase 2 traceability (14–19) is
    documented in `docs/exec-plans/completed/2026-08-26-phase2-items-14-19-mapping.md`
    (design-derived).

1. **Visit product line retirement (legacy schema only):** `visits`,
   `visit_product_sections`, `visit_defect_notes`, and nullable `anomalies.visit_id`
   remain for existing data; `visit_defect_notes` rows are read-only compatible.
   Product UI does not expose visit create/edit/preview dialogs, defect-note
   editors, visit event scopes, visit statistics/export paths, Supplier 360 visit
   tabs, visit linking controls, or a separate `登錄訪廠缺失` entry. Do not infer new
   visit defect notes from warehouse records. Repository visit CRUD and
   `sync_visit=True` are test/script opt-in only. See
   `docs/exec-plans/completed/retire-visit-product-line.md`.
2. Visit or audit defects must never be inserted into `defect_records`.
3. Warehouse nonconforming-product records describe physical inventory items and
   must never become supplier events without a separate, explicit event record.
4. ERP/Excel master imports update only shared master data plus import audit
   rows. They must not create visits, anomalies, visit defect notes, or warehouse
   defect records.
5. Warehouse pending workflow split is data-backed by
   `defect_records.processing_line`, not by labels, hidden UI filters,
   `category`, or `return_slip_type`. Runtime values are `原物料`, `委外加工`, and
   migrated/cleanup-only `未分流`. New and edited rows must save as `原物料` or
   `委外加工`; existing rows default to `未分流` until a user classifies them.
6. `defect_records.supplier_id` is a nullable read-model relationship to the
   shared `suppliers.id`. It is backfilled only by exact supplier-name matches;
   unmatched legacy rows remain NULL. This relationship supports supplier 360
   projections but does not merge warehouse records into supplier-event tables,
   statistics, or exports.
7. Supplier 360 is a read-only aggregation over `anomalies` and
   `defect_records`. Legacy `visits` rows are not exposed in product UI. Every
   projected row keeps its source label and source identifier. The NCR-to-anomaly
   action is an explicit user action and records `anomalies.source_defect_no` for
   traceability; it does not mutate or delete the originating warehouse record.
8. Repeat Issue similarity is supplier-event scoped only. Canonical storage is
   `anomaly_repeat_links` (directed `anomaly_id` → `peer_anomaly_id` with
   deterministic `similarity_score` and newline-delimited `match_reasons`).
   Scoring SSOT is `repeat_issue_scoring.py`; refresh runs per supplier on
   anomaly create/update and during `anomaly_repeat_links_v1` backfill. The
   workbench `RepeatIssuesPanel` and Supplier 360 `repeat_flagged_anomaly_count`
   are read-only projections over this index. Warehouse `defect_records` are not
   indexed for repeat similarity.
9. Manager View is a supplier-event operational read model only. Canonical
   projection for the manager summary table is `list_manager_summary_rows()`
   (overview SSOT quality columns). The open-action operational queue uses
   `list_operational_action_queue()` on the sidebar `處置項目` page, not inside
   `ManagerViewPage`. The manager page is separate from event query/list scope
   chips and does not merge warehouse NCR rows.

## Supplier Anomaly Quality-Report Requirement

- `anomalies.quality_report_required` is the nullable source of truth for
  「品質異常單要求」: `1` means 是, `0` means 否, and `NULL` means a legacy row
  that has not been classified. Schema upgrades add the column without
  backfilling or guessing historical values.
- `NewAnomalyDialog` requires an explicit 是／否 selection before a new or
  edited anomaly can be saved. Read-only preview preserves the stored state.
- `EventListWidget` displays 「品質異常單要求」 for supplier-event anomaly rows:
  是／否／未設定 from `quality_report_required`. Visit product UI is retired; legacy
  `visits` rows remain in SQLite only.
- Supplier-event Excel detail output lists anomaly rows only (`類型` = `異常`).
  Legacy visit rows are not exported through product paths. The `異常` sheet exports
  是／否／未設定 for 「品質異常單要求」 and keeps raw 「異常類別」 separate from 「原因分類」.

## Supplier Anomaly Category and Source Lexicons

- `ui_settings.supplier_event.anomaly_categories.v1` stores the user-maintainable
  anomaly category list used by `NewAnomalyDialog`, appearance default category,
  and service-layer validation. The form is strict: categories must come from the
  lexicon or remain blank (`未分類` in statistics).
- `ui_settings.supplier_event.anomaly_sources.v1` stores anomaly source entries
  with stable `id`, display `label`, and per-source ERP trace visibility/required
  field sets. `anomalies.anomaly_source` persists the label text.
- Both lexicons are maintained from **顯示設定 → 表單與業務** alongside the SMT
  process keyword library. Deleting a lexicon item is blocked when existing
  `anomalies` rows still reference that label.
- `anomaly_trace_contract.normalize_anomaly_source()` and trace-field helpers
  resolve against the saved source lexicon, with legacy label mapping retained for
  older rows.

## Supplier Anomaly SMT Process Keywords

- `anomalies.process_keywords` stores optional multi-value SMT process keywords as
  newline-delimited text. It is independent from `anomalies.category` and must not
  be merged into warehouse NCR data or the category Pareto.
- `NewAnomalyDialog` exposes keyword entry through `TagInputWidget`; users may pick
  presets from `ui_settings.smt.process_keywords.v1` or enter custom keywords.
- Keyword statistics use `get_anomaly_process_keyword_pareto_by_range` as the single
  implementation for the stats page chart and Excel export sheet/chart PNG.

## Supplier Anomaly ERP Trace Numbers

- `anomalies.anomaly_source` persists a label from the user-maintainable source
  lexicon (`ui_settings.supplier_event.anomaly_sources.v1`). Built-in defaults
  mirror the former six-value set:
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
- The same rule applies to standalone anomalies and legacy rows that already
  carry `anomalies.visit_id` from schema history. Creating a visit or visit
  defect note alone does not create this folder; visit product UI is retired.
- Folder creation is idempotent. Windows-invalid filename characters in the
  supplier-name component are replaced with `_`; the stored supplier name and
  anomaly number are never changed.
- Each folder contains a same-stem `.md` file whose body is deterministic YAML.
  All user-facing keys use Traditional Chinese. The canonical field order is owned by
  `src/services/event/_anomaly_markdown.py`; absent scalar values remain as
  empty strings and `attachments` remains an explicit list. Attachment entries
  contain both filename and caption.
- The service layer overwrites the YAML snapshot after create, edit, legacy
  `visit_id` linkage updates (repository opt-in only), close, closure-date
  adjustment, reopen, and attachment mutations.
  SQLite and the attachment store remain authoritative; the Markdown file is a
  synchronized operational snapshot, not a second writable data source.

## UI Entrypoint And Folder Boundaries

- The app has one daily desktop shell: `main.py` with `src/ui/main_window.py`.
- The sidebar grouping expresses workflow structure, not data ownership: four
  domain group headers (text labels) — 供應商事件, 倉庫不合格品, 資料庫設定, 系統 — organize
  supplier-event create/query/operational-queue/statistics pages; 倉庫不合格品 holds 建立不合格品 /
  待處理委外加工 / 待處理原物料 / 歷史紀錄 / 不合格品統計分析; 資料庫設定 holds 供應商總覽 /
  原物料供應商 / 委外加工 / 原物料 / 半成品/成品（後四項為並排雙欄導覽，分「供應商主檔」「料號主檔」兩組 pill 標籤底色；UI 標籤 SSOT 見 `sidebar_nav.py`）
  (`PAGE_MASTER_RAW_SUPPLIER` … `PAGE_MASTER_SEMI_FINISHED`; legacy `PAGE_MASTER` → raw supplier);
  系統 holds 顯示設定 as a lazy-loaded full page in the main content stack. Supplier-event query scopes are page-local chips on the single 事件查詢 page (單獨異常 / 已結案), not
  first-class sidebar rows. The consolidated **作業佇列** sidebar row hosts four
  operational chips (逾期案件 / 根因待查 / 處置項目 / 案件總覽) backed by
  `get_supplier_event_queue_counts` and embedded queue/manager views; legacy
  PAGE_KEY aliases (`PAGE_EVENT_OVERDUE`, `PAGE_EVENT_ROOT_CAUSE`,
  `PAGE_EVENT_OPEN_ACTIONS`, `PAGE_MANAGER_VIEW`) route to the same stack index
  and force the matching chip. The retired home hub and sidebar `首頁` row are not
  product navigation.
- The sidebar emits `nav_activated(action)` (`("page", PAGE_KEY)` or
  `("scope", EVENT_SCOPE_*)`); `MainWindow._PAGE_KEY_TO_INDEX` maps PAGE_KEY to the
  stack index, so the sidebar stays decoupled from stack indexes.
- Stack index `0` remains a retired ghost placeholder; `EVENT_OPS_PAGE_INDEX`
  follows `SUPPLIER_360_PAGE_INDEX`, and `APPEARANCE_SETTINGS_PAGE_INDEX` is appended
  after it. Earlier indexes (`1` 事件查詢 / `2` 異常事件統計 / `3` 建立不合格品 …)
  are unchanged; `ncr.embed.NCR_PAGE_OFFSET` is not shifted.
  When indexes change, update the index constants, legacy aliases
  (`EVENT_CREATE_ANOMALY_PAGE_INDEX`), `_PAGE_KEY_TO_INDEX`,
  `ncr.embed.NCR_PAGE_OFFSET`, and the
  affected tests in the same change.
- Supplier-event sidebar badges: `事件查詢` remains the unscoped open-anomaly
  total. Operational queue counts (`逾期案件`, `根因待查`, `處置項目`) display on
  **作業佇列** page chips via `get_supplier_event_queue_counts` (COUNT=LIST); the
  作業佇列 sidebar row has no badge. Opening the anomaly workbench from a queue
  row keeps the ops page active with the matching chip (`source_page_key`).
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
- SQLite persistence for v2 is split under `src/database/` while keeping
  `database.repository` as the backward-compatible facade: `schema_bootstrap.py`,
  `supplier_repository.py`, `product_repository.py`, `anomaly_repository.py`,
  `anomaly_workbench_repository.py`, `visit_legacy_repository.py`, and
  `event_query_repository.py`. Services, tests, and scripts must continue to
  import public APIs from `database.repository` unless a future migration plan
  explicitly retargets callers. Satellite repos (`case_action_repository`,
  `anomaly_hypothesis_repository`, `anomaly_repeat_repository`,
  `manager_view_repository`) remain separate domain modules re-exported by the
  facade.

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
  `處置項目數`, `根本原因狀態`, `改善措施狀態`, `有效性驗證`, `附件數`,
  `原因假設數`, `已採納假設`, `重複警示`) after the existing legacy fields.
  Range Excel may add a「原因假設」sheet with up to 12 embedded hypothesis-tree
  PNGs when `export_include_charts` is enabled. Event PDF and Markdown snapshots
  consume the same overview card; weekly PPTX overdue highlighting uses overview
  `overdue`, not `anomalies.due_date` alone. Manager view Excel and supplier
  quarterly reports are separate supplier-event exports and must not merge NCR rows.
- VISIT rows are intentionally not enriched; only ANOMALY rows own the workbench
  sub-tables and the parity rules. Product event query no longer lists VISIT rows.
- `list_anomaly_analysis_notes` and hypothesis evidence-chain attachment badges
  use live `anomaly_attachments` COUNT by `related_note_id`; do not trust stored
  `anomaly_analysis_notes.attachment_count`.
- Manager-view and other `list_column_contract` exports must use the same display
  strings as the page table renderer (e.g. `overdue` → `逾期`/`—`); see
  `tests/test_exports_phase7.py`.

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
- `case_actions_v1` is an explicit high-risk promotion, not an implicit startup
  migration for an existing formal database. Before writable bootstrap,
  `initialize_database()` opens an existing formal DB read-only and fails closed
  with 「需要完成資料升級」 when the required version is missing. Fresh DBs may
  receive the current schema; existing disposable DBs may migrate only when
  `SQE_REQUIRE_DISPOSABLE_DB=1`. The repository also resolves
  `PRAGMA database_list` and refuses a formal main path, so the disposable flag
  alone cannot bypass the boundary. Formal migration requires both explicit
  promotion markers.
- Formal promotion requires the application to be closed, a verified SQLite
  online backup, pre-migration schema/count/relation evidence, one transactional
  idempotent migration, `PRAGMA integrity_check`, `PRAGMA foreign_key_check`,
  lineage/count/status reconciliation, and a focused smoke. Failure restores the
  entire pre-migration backup with the preceding application version; partial
  reverse SQL is not a rollback strategy.
- Focused, Full, Phase 1 native visual, and baseline-refresh wrappers fingerprint
  the formal DB's complete logical schema and rows before and after execution.
  Physical WAL/checkpoint byte changes are ignored, but any logical field or
  schema change fails the gate.
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
  3. **表單業務預設 (Form & Business Defaults)**: `default_responsible_person` (`str`), `default_anomaly_category` (`str`), `default_due_days` (`7` / `14` / `30`). Visit-create preference fields (`default_sync_visit`, `default_visit_type`, `default_visit_time_slot`) were removed in v10; legacy v9 JSON still loads with those keys ignored.
  4. **匯出與報告 (Export & Reports)**: `default_export_dir` (`str`), `export_completion_action` (`open_file` / `open_folder` / `notify_only`), `report_organization_header` (`str`), and `export_include_charts` (`bool`).
  5. **系統與備份 (System & Backup)**: `default_startup_page` (`events` / `defects` / `stats`; legacy `home` migrates to `events`), `auto_backup_prompt` (`bool`), `backup_retention_count` (`5` / `10` / `20` / `30`), and `confirm_on_delete` (`bool`).
- Valid legacy `appearance.preferences.v1`, `v2`, `v3`, and `v4` payloads map in memory to v5 defaults for newly added fields; missing, malformed, unknown-key, or unknown-value payloads resolve to the default profile without rewriting stored data.
- This preference never changes core event, warehouse, statistics, export, or navigation data. Existing NCR keys, including `defect_list_columns`, remain compatibility-owned by the NCR module.

## Startup Performance And Lazy Loading Boundaries

- Heavy third-party libraries (`openpyxl`, `reportlab`, `matplotlib`) must never be imported statically at module root in services or UI classes loaded during startup. Always import them inside the specific function or method where they are invoked.
- Module-level style instantiation is prohibited; style objects (e.g. `Font()`, `PatternFill()`, `Border()`) must be encapsulated in cached helper functions (e.g. in `src/ui/export_helpers.py`).
- Container pages wrapping full forms (such as `EventCreatePage` and `LazyPageWidget`) must support lazy initialization (`lazy_load=True`) and defer child form creation to `_ensure_form_installed()` on first `showEvent`.
- Avoid redundant `refresh_data()` queries during `MainWindow._setup_ui` when child widgets already load initial data in `__init__`.
- In UI files, maintain service module imports (e.g. `from ncr.services import export_service`) at module level while keeping the service file itself lazy-loading external heavy dependencies. This guarantees `unittest.mock.patch` stability in tests while eliminating startup latency.

