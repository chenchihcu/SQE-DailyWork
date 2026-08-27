# SQE DailyWork Desktop

## Product Positioning

`SQE DailyWork` is the single local desktop main program for daily Supplier
Quality Engineering work. It behaves like an ERP-style workbench: one app shell
opens different workflows from the sidebar and home workbench.

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

### Windows packaged build (1.1.0+)

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

- Home is a daily cockpit centered on one read-only backlog (待辦) list
  (open/overdue anomalies, overdue first). KPI cards stay retired from the
  visible home layout. The backlog footer exposes warehouse pending shortcuts
  for `待處理委外加工`, `待處理原物料`, and `未分流待整理`; each shortcut only reads
  existing services and routes through existing navigation.
- Sidebar is workflow-first with domain groups: 首頁; 供應商事件 (新增訪廠 /
  新增異常 / 事件管理 / 異常事件統計); 倉庫不合格品 (建立不合格品 /
  待處理委外加工 / 待處理原物料 / 歷史紀錄 / 不合格品統計分析); 供應商管理
  (供應商總覽 / 基礎資料); 系統 (顯示設定). 事件管理頁內以 scope chips 切換
  單獨異常 / 訪廠發現異常 / 訪廠紀錄 / 已結案；側欄 `事件管理` badge 為全部待處理異常總數。
- Supplier event pending work surfaces on the `事件管理` sidebar badge (all open
  supplier anomalies). Per-scope counts appear on the event page chips. Warehouse
  nonconforming-product pending work surfaces as two separate badges: one for
  `status <> '已結案' AND processing_line = '委外加工'`, and one for
  `status <> '已結案' AND processing_line = '原物料'`. `未分流` is shown as a
  cleanup warning/to-do, not merged into either formal badge.
- `新增訪廠` / `新增異常` 是側欄與事件工具列可進入的獨立工作頁；儲存後顯示
  `查看清單`／`繼續新增`，未儲存的離頁操作會先確認。清單中的編輯與預覽仍維持對話框。
- 相容的 `open_new_visit_defect_dialog()` 呼叫一律導向「新增訪廠」全頁，不再開啟
  建立用 modal；建立頁以共用 `CreateWorkflowShell` 呈現同一份
  `NewAnomalyDialog`／`NewVisitDialog` 欄位與驗證邏輯，清單中的編輯與預覽仍使用其
  固定 footer 的 modal 呈現。
- `新增訪廠` / 編輯訪廠使用同一套表單內容，以縱向「基本資訊」與「活動摘要」卡片呈現；
  表單不再提供訪廠缺失輸入。編輯舊訪廠時會保留既有缺失與產品區段資料，
  避免只更新一般欄位便清除歷史紀錄。
- 正式供應商異常由 `新增異常` 流程建立；既有 `visit_defect_notes` 仍保留於資料庫、
  查詢／報表與明確轉換為正式異常的契約中，但目前沒有新的訪廠缺失輸入控制。
- Supplier anomaly closure uses the user-selected `closed_at` date from the
  close dialog; closed anomalies can adjust that date without reopening, and
  supplier-event trend charts group closures by the same date.
- `建立不合格品`, `待處理委外加工`, `待處理原物料`, and `歷史紀錄` open the embedded warehouse
  nonconforming-product workflow pages inside the same main window.
- `不合格品統計分析` opens warehouse nonconforming-product statistics charts
  and proportion analysis.
- `基礎資料` manages shared suppliers and products. Product import accepts
  Excel/ERP exports for shared `suppliers/products` after preview and backup.
- Statistics pages keep scroll guards, visible scrollbars, long-name tooltips,
  color-readable chart/status roles, and native dense-chart visual checks.
  `異常事件統計` is a dashboard view without visible page tabs or
  decision-summary cards.
- `顯示設定` uses finite tabs for 5 domain categories (外觀主題／視覺表格與互動／表單業務預設／匯出與報告／系統與備份), with fixed
  preview/save/cancel actions and no whole-dialog content scrollbar. Supplier-event
  and warehouse lists use a responsive `重點欄位` view at constrained widths and
  a reversible `完整欄位` view for all source fields, along with multi-type table column
  auto-sorting and sort state persistence. This changes only on-screen
  presentation: personal NCR column order, database records, and Excel/PDF exports
  remain unchanged; complete mode keeps a visible horizontal scrollbar when needed.

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
- `visits`
- `visit_product_sections`
- `visit_defect_notes`
- `monthly_stats_cache`
- anomaly attachments under `data/attachments/anomaly/{anomaly_id}/`

Warehouse physical nonconforming-product data:

- `defect_records`
  - `processing_line`: `原物料`, `委外加工`, or migrated/cleanup-only `未分流`.
    New and edited records must use `原物料` or `委外加工`; existing rows default
    to `未分流` until deliberately classified.
- `ui_settings`
  - 本機全域顯示與系統偏好使用 `appearance.preferences.v5` key，保存包含外觀主題（密度、側欄密度、強調色、字體縮放、高對比）、視覺表格與互動（表格密度、交替行底色、格線、分頁上限、動畫、雙擊行為、搜尋模式、統計月份跨度、柏拉圖門檻線）、表單業務預設（責任人、類別、同步訪廠、到期天數、訪廠時段）、匯出與報告（目錄、完成動作、抬頭、包含圖表）、系統與備份（啟動頁面、關閉備份提示、備份保留數、刪除確認）共 27 項欄位；舊版 v1~v4 在記憶體中平滑相容載入。此設定只影響本機顯示與預設行為，不破壞任何 SQE 歷史資料。
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
- Visit/audit defect conversion into `anomalies.visit_id` without writing
  `defect_records`.
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
