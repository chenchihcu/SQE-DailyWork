# SQE DailyWork Desktop

## Product Positioning

`SQE DailyWork` is the single local desktop main program for daily Supplier
Quality Engineering work. It behaves like an ERP-style workbench: one app shell
opens different workflows from the sidebar.

The two daily workflow lines are intentionally separated:

- Supplier event management: supplier anomalies, supplier visits, supplier
  audits, and visit/audit defect notes.
- Warehouse nonconforming-product management: physical products held in the
  nonconforming-product warehouse.

Supplier and product master data are shared company data. Workflow records and
statistics remain separated by source.

## Main Entry

```powershell
python main.py
.\run_app.bat
```

### Windows packaged build (1.2.0+)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

The build produces `dist\SQE_DailyWork\SQE_DailyWork.exe` and a portable zip at
`dist\SQE_DailyWork-win64.zip`. Runtime data (`data\`, `Outputs\`, `logs\`)
lives beside the executable in the distribution folder. To migrate an existing
installation, copy your `data\` and `Outputs\` folders into the same directory
as `SQE_DailyWork.exe`. The installer does not embed a production database.

Requirements: Windows 10/11 x64 with Traditional Chinese fonts installed.

Portable install QA: `scripts\portable_install_smoke.ps1` (unpack zip → scratch DB
smoke). Manual checklist: `docs\release\portable-install-checklist.md`.

The repository root is the application root. There is no outer launcher layer,
no separate launcher window, and no standalone NCR main window.

## UI Workbench

- Default startup opens **事件查詢** (`default_startup_page=events`). Legacy `home`
  preference values migrate to `events` on load.
- Sidebar is the sole workflow navigation surface with domain groups: 供應商事件
  (新增異常 / 事件查詢 / 作業佇列 / 異常事件統計); 倉庫不合格品 (建立不合格品 /
  待處理委外加工 / 待處理原物料 / 歷史紀錄 / 不合格品統計分析); 資料庫設定
  (供應商總覽 / 原物料供應商｜委外加工 / 原物料｜半成品/成品 並排主檔列); 系統 (顯示設定). 事件查詢頁內以 scope chips 切換
  單獨異常 / 已結案；側欄 `事件查詢` badge 為全部待處理
  異常總數。作業佇列頁內 chips 切換 逾期案件 / 根因待查 / 處置項目 / 案件總覽，
  chip `(N)` 使用 `get_supplier_event_queue_counts`。
- Supplier event pending work surfaces on the `事件查詢` sidebar badge (all open
  supplier anomalies). Operational queues live on the consolidated `作業佇列`
  page (chips for overdue / root-cause / open actions / manager summary). Per-scope
  counts appear on the event page chips. Warehouse
  nonconforming-product pending work surfaces as two separate badges: one for
  `status <> '已結案' AND processing_line = '委外加工'`, and one for
  `status <> '已結案' AND processing_line = '原物料'`. `未分流` is shown as a
  cleanup warning/to-do, not merged into either formal badge.
- `新增異常` 是側欄可進入的獨立工作頁；儲存後顯示 `查看清單`／`繼續新增`，未儲存的
  離頁操作會先確認。清單中的編輯與預覽仍維持對話框／工作台路由。
  產品不再提供「新增訪廠」頁面或工具列入口；新增異常也不再同步 INSERT `visits`。
- 建立頁以共用 `CreateWorkflowShell` 呈現 `NewAnomalyDialog` 欄位與驗證邏輯。
  訪廠產品 UI（事件 scope、編輯對話框、統計圖、Supplier 360 分頁、全域搜尋與獨立 PDF/Excel）已退役；
  `visits` / `visit_defect_notes` / `anomalies.visit_id` 僅保留 legacy schema 與資料。
- Supplier anomaly closure uses the user-selected `closed_at` date from the
  close dialog; closed anomalies can adjust that date without reopening, and
  supplier-event trend charts group closures by the same date.
- 案件工作台（Phase 4）提供七個分頁：概況、歷程、分析（含多層原因假設樹）、8D、
  改善措施、附件與變更紀錄；結案／重開走 header 與 footer 閘控，並寫入
  `CASE_CLOSED` / `CASE_REOPENED` audit。
- 重複案件警示（Phase 5）以 `anomaly_repeat_links` 索引同供應商相似歷史異常；
  工作台 `RepeatIssuesPanel` 與 Supplier 360 `repeat_flagged_anomaly_count` 共用
  scoring SSOT，且不納入倉庫 `defect_records`。
- `案件總覽`（Phase 6）提供案件品質狀態總覽（含已結案、品質三欄、匯出）；逾期案件、
  根因待查、處置項目與案件總覽皆在側欄 **作業佇列** 頁內以 chips 切換。摘要列 enriched
  `get_anomaly_overview_card()`；逾期篩選與 KPI 與 case-action 到期日 SSOT 一致，不含 NCR 列。
- 匯出／週報（Phase 7）讓 Excel／PDF／Markdown／PPTX 共用 overview read-model；
  區間 Excel「異常」工作表含追溯欄位與假設樹 PNG（最多 12 案）；案件總覽可匯出
  案件總覽 Excel 單一工作表。
- 案件工作台的「下一步處置」與「改善措施」共用 canonical `case_actions`。
  Action 類型為 `NEXT_ACTION / CONTAINMENT / CORRECTION / CORRECTIVE_ACTION /
  SYSTEMIC_IMPROVEMENT`，執行狀態只使用 `已規劃 / 執行中 / 已完成 / 已取消`；
  有效性狀態由 Action 類型、`verification_required` 與最新一筆 append-only
  `action_verifications` 推導。完成執行不等於有效性通過，`無效` 也不會把
  Action 自動改回執行中。
- `建立不合格品`, `待處理委外加工`, `待處理原物料`, and `歷史紀錄` open the embedded warehouse
  nonconforming-product workflow pages inside the same main window.
- `不合格品統計分析` opens warehouse nonconforming-product statistics charts
  and proportion analysis.
- `資料庫設定`（側欄群組標籤）管理 shared suppliers and products. Product import accepts
  Excel/ERP exports for shared `suppliers/products` after preview and backup.
- Statistics pages keep scroll guards, visible scrollbars, long-name tooltips,
  color-readable chart/status roles, and native dense-chart visual checks.
  `異常事件統計` is a dashboard view without visible page tabs or
  decision-summary cards.
- `顯示設定` is a lazy-loaded full page in the main content stack. It uses finite
  navigation for 5 domain categories (外觀主題／視覺表格與互動／表單業務預設／匯出與報告／系統與備份),
  with live preview and fixed reset/save/discard actions. Saving stays on the page;
  discarding restores the last persisted preview. Each category owns its vertical
  scroll area, and the page reflows from two columns to one at constrained widths. Supplier-event
  and warehouse lists use a responsive `重點欄位` view at constrained widths and
  a reversible `完整欄位` view for all source fields, along with multi-type table column
  auto-sorting and sort state persistence. This changes only on-screen
  presentation: personal NCR column order, database records, and Excel/PDF exports
  remain unchanged; complete mode keeps a visible horizontal scrollbar when needed.
  **表單與業務** tab also exposes **管理異常類別辭庫** / **管理異常來源辭庫** for
  `ui_settings` lexicon maintenance consumed by anomaly forms and trace validation.

## Runtime Architecture & Performance

- UI: PySide6 desktop app in `main.py`.
- UI shell: `src/ui/main_window.py`, `src/ui/sidebar_nav.py`, and page widgets under
  `src/ui/widgets/`.
- Shared UI tokens and QSS: `src/ui/theme.py`, `src/ui/layout_constants.py`,
  `src/ui/status_colors.py`, `src/ui/export_helpers.py`, and `src/ui/widgets/common_widgets.py`.
- Startup performance & lazy loading: Heavy 3rd-party libraries (`openpyxl`, `reportlab`,
  `matplotlib`) are imported lazily inside operational methods rather than at module root;
  container form pages leverage `src/ui/widgets/lazy_page_widget.py` (e.g. `EventCreatePage`)
  to defer child widget creation to first `showEvent`, preventing cold-start latency.
- Active DB: local SQLite `data/sqe_v2.db`.
- Archived legacy NCR source DB: `ncr/data/defect.db.migrated`.
- Supplier event service: `src/services/event_service.py`.
- Shared master import service: `src/services/master_import_service.py`.
- Warehouse nonconforming-product module: `src/ncr/embed.py` plus `src/ncr/services/`.

## Folder Structure

Source and runtime folders have separate responsibilities:

| Folder | Responsibility |
| --- | --- |
| `src/ui/` | Main Qt shell, sidebar, theme, layout constants, export helpers, and page widgets. |
| `src/services/` | Supplier event, import, export, and reporting application services. |
| `src/database/` | SQLite connection, repository, migration, and DB boundary code. |
| `src/ncr/` | Embedded warehouse physical nonconforming-product workflow source. |
| `scripts/` | Verification, migration, visual probe, report, and helper entrypoints. |
| `tests/` | Focused regression, layout, visual-structure, and workflow boundary checks. |
| `docs/` | Architecture, UI/theme, execution-plan, risk, and harness documentation. |
| `data/`, `Outputs/`, `scratch/` | Local runtime data, generated exports, and temporary visual/debug artifacts; not source-of-truth docs. |

Use `docs/README.md` as the documentation index before adding new documents.
Keep implementation under the owning source folder instead of adding new root
folders for a workflow that already has an owner.

## Data Boundary

Shared master data:

- `suppliers`
- `supplier_contacts`
- `products`
- `product_stage_change_logs`

Supplier event workflow data:

- `anomalies`
- `case_actions`（案件下一步、圍堵、立即矯正、矯正及系統改善的唯一新寫入真理）
- `action_verifications`（已完成且需要驗證之 Action 的 append-only 驗證紀錄）
- `case_action_legacy_map`（舊 Action ID 到 canonical ID 的 deterministic lineage）
- `anomaly_analysis_notes`, `anomaly_root_causes`, `anomaly_attachments`,
  `anomaly_eight_d_reviews`, `anomaly_audit_logs`
- `anomaly_attachments` metadata uses canonical `related_action_id` and
  optional `related_note_id`; `related_ca_id` remains a legacy migration
  lineage field. `file_type` and `uploaded_by` are system metadata. Existing
  Traditional-Chinese category values remain readable while new callers use
  the nine attachment categories defined by the incident-management contract.
- legacy `anomaly_actions`, `corrective_actions`, `effectiveness_verifications`
  只保留為 migration／rollback snapshot；升級後的新版本不得再寫入
- `visits`
- `visit_product_sections`
- `visit_defect_notes`
- `monthly_stats_cache`
- anomaly attachments under `data/attachments/anomaly/{anomaly_id}/`; SQLite
  owns attachment metadata while the filesystem adapter owns bytes. Existing
  `captions.json` and image-only APIs remain compatible. Legacy physical-only
  files are exposed as read-only projections until an approved reconciliation
  migration registers them; they are never assigned guessed links or authors.

Warehouse physical nonconforming-product data:

- `defect_records`
  - `processing_line`: `原物料`, `委外加工`, or migrated/cleanup-only `未分流`.
    New and edited records must use `原物料` or `委外加工`; existing rows default
    to `未分流` until deliberately classified.
- `ui_settings`
  - 本機全域顯示與系統偏好使用 `appearance.preferences.v10` key（v1~v9 平滑升級），
    含外觀、表格互動、表單業務預設（責任人、類別、到期天數等）、匯出與系統維護設定。
  - 既有 NCR 欄位排序 key（例如 `defect_list_columns`）維持相容且不可被全域顯示偏好覆寫。
- warehouse-module compatibility support tables such as `product_records`

Import audit data:

- `import_batches`
- `import_batch_rows`

Visit/audit defect notes are supplier event records. They must not be inserted
into `defect_records`. Warehouse nonconforming-product statistics must query
`defect_records`; supplier event statistics must query supplier event tables.

## Import And Migration

- Legacy `data/sqe.db` migration remains handled by `src/database/migration.py`.
  It is all-or-nothing: any row error rolls back the batch, does not write
  `legacy_migrated`, and emits a `*_migration_VERIFY.json` reconciliation file.
- Legacy NCR `ncr/data/defect.db` was migrated once into `data/sqe_v2.db` by
  `src/database/ncr_migration.py`; the old source is archived as
  `ncr/data/defect.db.migrated`. Warehouse schema upgrades backfill
  `defect_records.processing_line` to `未分流` for existing rows without guessing
  their formal processing line.
- Shared product master import is implemented in
  `src/services/master_import_service.py`. It writes only `suppliers/products` after
  preview, conflict checks, and DB backup, then records the attempt in
  `import_batches/import_batch_rows`. Duplicate identity is
  `(supplier, product_code)`; an existing stage mismatch is a blocking conflict
  that must use the normal product-stage change flow.
- Warehouse compatibility import services under `src/ncr/services/` are retained
  for warehouse-module support data and must be labeled as warehouse-scoped.
- `case_actions_v1` 是明確升級，不會在既有正式資料庫的一般啟動流程中偷偷套用。
  未完成升級的新版本會 fail closed 並提示「需要完成資料升級」。正式套用必須先
  關閉應用程式、建立並驗證 SQLite online backup，在單一 transaction 執行
  idempotent migration，完成 `integrity_check`、`foreign_key_check`、lineage／筆數
  reconciliation 及 focused smoke；失敗時以完整備份與前一版本回復。Repository
  會從 SQLite connection 的實際 main path 辨識正式 DB，disposable flag 不能繞過；
  Promotion CLI 同時要求 promotion 與 apply-confirmation marker。Focused、Full 與
  Phase 1 native/baseline wrappers 會比對正式 DB 的 schema + 全表資料邏輯指紋，
  任一正式資料變化都使 gate 失敗。
- `anomaly_attachments_contract_v1` 同樣為明確升級：未完成時新版本 fail closed
  並提示「需要完成附件資料升級」。正式套用使用
  `scripts/apply_anomaly_attachments_promotion.ps1`（dry-run 預設；`-Apply` 需
  `SQE_ANOMALY_ATTACHMENTS_PROMOTION_APPROVED=1` 與 `SQE_DAILYWORK_CONFIRM_APPLY=1`
  及使用者核准）。Focused gate：
  `scripts/verify_attachments_phase2.ps1`。
- `anomaly_hypotheses_v1` 為 Phase 3 明確升級：未完成時新版本 fail closed
  並提示「需要完成 Hypothesis 資料升級」。正式套用使用
  `scripts/apply_anomaly_hypotheses_promotion.ps1`（dry-run 預設；`-Apply` 需
  `SQE_ANOMALY_HYPOTHESES_PROMOTION_APPROVED=1` 與 `SQE_DAILYWORK_CONFIRM_APPLY=1`
  及使用者精確回覆 `繼續`）。Focused gate：
  `scripts/verify_hypothesis_phase3.ps1`。
- `product_records_view_is_active_v1` 為 Phase 8 NCR 相容 VIEW 修正：正式套用使用
  `scripts/apply_product_records_view_promotion.ps1`（dry-run 預設；`-Apply` 需
  `SQE_PRODUCT_RECORDS_VIEW_PROMOTION_APPROVED=1` 與 `SQE_DAILYWORK_CONFIRM_APPLY=1`
  及使用者核准）。Focused gate：`tests/test_product_records_view_write_path.py`。

Bulk ERP imports, schema migrations, and destructive cleanup require backup,
dry run, reconciliation, and focused verification.

## Outputs

- Each newly created supplier anomaly, including a visit defect confirmed as a
  formal anomaly, creates or reuses `Outputs/ncr number file/<供應商名稱><異常單號>/`.
  Windows-invalid filename characters in the supplier name are replaced with
  `_`; the anomaly database transaction remains the source of truth.
- Each anomaly folder contains `<供應商名稱><異常單號>.md`, a deterministic YAML
  snapshot with Traditional Chinese field labels for every anomaly-detail field
  plus attachment filenames and captions. Missing scalar values remain present
  as empty strings, and boolean values display as `是` / `否`. The file is
  overwritten after anomaly edits, visit-link changes, closure-date changes,
  close/reopen actions, and attachment changes. SQLite is authoritative: a
  snapshot/folder failure returns success with a visible warning and may be
  repaired idempotently; users must not repeat the primary mutation.
- Event PDF export: `src/services/event_pdf_exporter.py` (with automatic ReportLab CJK font registration).
- Monthly Excel export: `src/services/event_service.py` (with lazy style caching via `src/ui/export_helpers.py`).
- Weekly PowerPoint report: `scripts/generate_weekly_report.py`.
- Warehouse nonconforming-product exports remain in `src/ncr/services/`.

## UI Layout And Theme Contract

- Main window sizing is centralized in `src/ui/layout_constants.py` and
  `src/ui/window_sizing.py`.
- Supported minimum desktop work area is 1024 x 680. First open targets
  1360 x 860, capped to the active screen.
- Dialog command buttons stay outside scrollable content.
- Offscreen Qt is structural smoke only. Visual review for Chinese text,
  typography, color hierarchy, and native fit should use
  `scripts/qt_visual_probe.py`.

## Validation

```powershell
.\scripts\verify.ps1
.\scripts\verify.ps1 -Profile Focused
.\scripts\verify.ps1 -Profile Release
```

`Full` is the default. Both profiles create a verified disposable database via
SQLite online backup, set `SQE_DB_PATH`, and fail fast if verification resolves
to the formal `data/sqe_v2.db`. Local `Full` additionally runs every manifest
target at 100% / 125% / 150% DPI plus required pixel baselines. GitHub Actions
and other clean clones pass `-AllowSchemaOnlySource` (no gitignored formal DB);
CI `Full` also passes `-SkipNativeVisual`. That skip is not visual evidence.
CI unittest uses `-v` and a 180s per-test hang abort (`SQE_TEST_HANG_SECONDS`);
a cancelled GitHub Actions job is not a passing gate.

## Backup

```powershell
.\scripts\backup_data.ps1
```

This backs up root `data/sqe_v2.db` and the archived NCR source database when
present. Active SQLite databases are copied with the SQLite online-backup API,
then reopened read-only for `integrity_check` and per-table count parity; raw
file copy is not used for WAL databases. The same verified helper is available
as `python scripts\sqlite_backup.py <source> <destination>`.

Focused checks should cover:

- One main window entrypoint and no standalone NCR main shell.
- Embedded warehouse `建立不合格品` / `待處理委外加工` / `待處理原物料` / `歷史紀錄` pages.
- `defect_records` count and migrated NCR business keys.
- Legacy visit schema (`visits`, `visit_defect_notes`, `anomalies.visit_id`) remains
  read-only compatible; product UI does not expose visit workflows or write visit
  rows from warehouse `defect_records`.
- Separated supplier event and warehouse nonconforming-product statistics.
- Shared product import preview/apply/backup behavior.
- UI/UX workbench checks with `scripts/qt_visual_probe.py` when visual fit,
  CJK text, or layout quality is part of the change.
- Sidebar information architecture, supplier/warehouse badges, visible
  scrollbars, color hierarchy, and statistics dense-chart fit.

Native visual probes:

```powershell
python scripts\qt_visual_probe.py --target main
python scripts\qt_visual_probe.py --target form-density
python scripts\qt_visual_probe.py --target stats-stress
python scripts\qt_visual_belt.py
```

The canonical target and DPI list lives in `scripts/qt_probe_targets.json`.
Required targets must have a matching `tests/visual_baseline/<target>/` manifest;
missing baselines are a gate failure, not a successful skip.
