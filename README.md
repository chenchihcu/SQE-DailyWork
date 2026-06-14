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

The repository root is the application root. There is no outer launcher layer,
no separate launcher window, and no standalone NCR main window.

## UI Workbench

- Home is a daily cockpit: six operational KPI cards plus one read-only backlog
  (待辦) list (open/overdue anomalies, overdue first, with a warehouse pending
  shortcut). Hero/cover content, feature tours, project-structure copy, and
  quick-entry write panels stay retired; the backlog list only reads existing
  services and routes through existing navigation.
- Sidebar is workflow-first with one item per group (首頁 / 事件管理 /
  異常事件統計 / 基礎資料 / 不合格品追蹤), conveyed by per-item icons and spacing
  rather than text section headers. The former 異常一覽表 / 訪廠紀錄一覽表 /
  異常已結案查詢 entries are now scope tabs (單獨異常 / 訪廠發現異常 / 訪廠紀錄 /
  已結案) inside the single 事件管理 page.
- Supplier event and warehouse nonconforming-product pending work both surface
  as sidebar badges.
- `登錄訪廠紀錄` and `登錄訪廠缺失` use the visit form.
- Visit/audit defect notes can be manually confirmed into formal supplier
  anomalies while retaining the `visit_id` link.
- `不合格品追蹤` opens the embedded warehouse nonconforming-product page inside
  the same main window.
- `基礎資料` manages shared suppliers and products. Product import accepts
  Excel/ERP exports for shared `suppliers/products` after preview and backup.
- Statistics pages keep tab-level scroll guards, visible scrollbars, long-name
  tooltips, color-readable chart/status roles, and native dense-chart visual
  checks.

## Runtime Architecture

- UI: PySide6 desktop app in `main.py`.
- UI shell: `src/ui/main_window.py`, `src/ui/sidebar_nav.py`, and page widgets under
  `src/ui/widgets/`.
- Shared UI tokens and QSS: `src/ui/theme.py`, `src/ui/layout_constants.py`,
  `src/ui/status_colors.py`, and `src/ui/widgets/common_widgets.py`.
- Active DB: local SQLite `data/sqe_v2.db`.
- Archived legacy NCR source DB: `ncr/data/defect.db.migrated`.
- Supplier event service: `src/services/event_service.py`.
- Shared master import service: `src/services/master_import_service.py`.
- Warehouse nonconforming-product module: `src/ncr/embed.py` plus `src/ncr/services/`.

## Folder Structure

Source and runtime folders have separate responsibilities:

| Folder | Responsibility |
| --- | --- |
| `src/ui/` | Main Qt shell, sidebar, theme, layout constants, and page widgets. |
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
- `ui_settings`
- warehouse-module compatibility support tables such as `product_records`

Import audit data:

- `import_batches`
- `import_batch_rows`

Visit/audit defect notes are supplier event records. They must not be inserted
into `defect_records`. Warehouse nonconforming-product statistics must query
`defect_records`; supplier event statistics must query supplier event tables.

## Import And Migration

- Legacy `data/sqe.db` migration remains handled by `src/database/migration.py`.
- Legacy NCR `ncr/data/defect.db` was migrated once into `data/sqe_v2.db` by
  `src/database/ncr_migration.py`; the old source is archived as
  `ncr/data/defect.db.migrated`.
- Shared product master import is implemented in
  `src/services/master_import_service.py`. It writes only `suppliers/products` after
  preview, conflict checks, and DB backup, then records the attempt in
  `import_batches/import_batch_rows`.
- Warehouse compatibility import services under `src/ncr/services/` are retained
  for warehouse-module support data and must be labeled as warehouse-scoped.

Bulk ERP imports, schema migrations, and destructive cleanup require backup,
dry run, reconciliation, and focused verification.

## Outputs

- Event PDF export: `src/services/event_pdf_exporter.py`.
- Monthly Excel export: `src/services/event_service.py`.
- Weekly PowerPoint report: `src/services/report_service.py` and
  `scripts/generate_weekly_report.py`.
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
```

## Backup

```powershell
.\scripts\backup_data.ps1
```

This backs up root `data/sqe_v2.db` and the archived NCR source database when
present.

Focused checks should cover:

- One main window entrypoint and no standalone NCR main shell.
- Embedded warehouse `不合格品追蹤` page.
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
```
