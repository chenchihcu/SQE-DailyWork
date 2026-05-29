# SQETOOL v2 (Desktop)

## Product Positioning
- Single-user local desktop tool (no login / no permission / no approval flow)
- Core flow:
  - 訪廠: `建立 -> 完成`，可同筆記錄多個產品區段與輕量 `缺失 / 改善` 紀錄
  - 正式異常: `建立 -> 結案`，保留給需要完整異常單與附件報告的情境
- Main workflow tabs:
  - 首頁
  - 訪廠紀錄
  - 訪廠發現異常
  - 單獨異常
  - 已結案
  - 統計分析
  - 基礎清單
- Home quick actions:
  - `登錄訪廠紀錄`: opens a blank visit record.
  - `登錄異常事件`: opens the same visit record form focused on lightweight defect notes.
  - Formal `新增異常` buttons in anomaly lists still open the formal anomaly form.

## Runtime Architecture
- UI: PySide6 desktop app (`main.py`)
- UI shell: `QTabWidget#MainWorkflowTabs` workflow tabs, shared MITCorp industrial inspection theme in `ui/theme.py`
- Brand boundary: MITCorp logo, deep-blue industrial palette, and videoscope-style visual elements are UI-only; database schema, service APIs, event payloads, and export fields follow the contract below.
- DB: local SQLite `data/sqe_v2.db`
- File storage: anomaly photos are stored under `data/attachments/anomaly/{anomaly_id}/`; `captions.json` stores per-photo captions.
- Data layer:
  - `database/connection.py`
  - `database/repository.py`
  - `database/migration.py`
  - `database/product_stage.py`
- Service layer:
  - `services/attachment_manager.py`
  - `services/event_pdf_exporter.py`
  - `services/event_service.py`
  - `services/report_service.py`

## Outputs
- Event PDF export: `services/event_pdf_exporter.py` includes formal anomaly reports and lightweight visit defect-note tables.
- Monthly Excel export: `services/event_service.py` writes `月統計`, `供應商排行`, and `明細` sheets.
- Weekly PowerPoint report: `services/report_service.py` launches `scripts/generate_weekly_report.py` and writes to `Outputs/`.

## UI Layout and Theme Contract
- Main window sizing is centralized in `ui/layout_constants.py` and applied through `ui/window_sizing.py`.
- Supported minimum desktop work area is 1024 x 680. The first-open default targets 1360 x 860, capped to about 95% of the active screen and never above 1920 x 1200.
- Dialogs keep command buttons outside the scrollable content area and are clamped to the active screen through `fit_dialog_to_available_screen`.
- Long visit-detail content scrolls inside the dialog body while the header and close button remain visible.
- Theme tokens, CJK-capable font selection, table styling, and status colors stay in shared UI modules (`ui/theme.py`, `ui/layout_constants.py`, `ui/status_colors.py`, and `ui/widgets/common_widgets.py`).
- Visual review for Chinese text, typography, and fit must use `scripts/qt_visual_probe.py` on the native Windows Qt platform. Offscreen Qt is structural smoke only.

## Database Contract (v2)
- `suppliers`
  - `id`, `supplier_name`, `contact_name`, `department`, `phone`, `contact_email`,
    `is_active`, `created_at`, `updated_at`
- `supplier_contacts`
  - `id`, `supplier_id`, `contact_name`, `department`, `phone`, `email`,
    `is_primary`, `created_at`, `updated_at`
- `products`
  - `id`, `product_code`, `product_name`, `product_stage(量產/試產)`,
    `supplier_id`, `secondary_supplier_id`, `is_active`, `created_at`, `updated_at`
- `anomalies`
  - `id`, `anomaly_no`, `anomaly_date`, `supplier_id`,
    `visit_id(optional FK->visits.id)`, `product_id(optional FK->products.id)`,
    `problem_desc`, `category`, `product_lot_no`, `product_name`, `product_stage`,
    `outsource_work_order`, `batch_qty`, `status(待處理/已結案)`,
    `improvement_desc`, `closed_by`, `root_cause_category`, `closed_at`,
    `pending_items`, `responsible_person`, `due_date`, `created_at`, `updated_at`
- `visits`
  - `id`, `visit_date`, `supplier_id`, `product_id(optional FK->products.id)`,
    `product_name`, `product_stage`, `visitor_name`, `summary`, `work_order_no`,
    `production_qty`, `tech_transfer`, tech-transfer item flags/states, `status(已完成)`,
    `created_at`, `updated_at`
- `visit_product_sections`
  - One visit-to-many product-section rows for same supplier/date/person visits.
  - `id`, `visit_id`, `product_id(optional FK->products.id)`, `product_code`,
    `product_name`, `product_stage`, `time_slot`, `work_order_no`,
    `production_qty`, `summary`, `sort_order`, `created_at`, `updated_at`
- `visit_defect_notes`
  - Lightweight on-site `缺失 / 改善 / 備註` notes, not formal anomaly tickets.
  - `id`, `visit_id`, `visit_product_section_id(optional FK->visit_product_sections.id)`,
    `defect_desc(required)`, `improvement_desc(optional)`, `note`, `sort_order`,
    `created_at`, `updated_at`
- `monthly_stats_cache`
  - `yyyymm`, `visit_count`, `closed_anomaly_count`, `updated_at`
- `migration_meta`
  - `key`, `value`, `updated_at`
- `product_stage_change_logs`
  - product-stage change audit rows plus synced anomaly/visit update counts

Attachments are not a database table. The image files and captions on disk are the source of truth.

## Migration
- Legacy DB: `data/sqe.db`
- New DB: `data/sqe_v2.db`
- Backup strategy:
  - On first migration, auto backup to `data/sqe_legacy_YYYYMMDD.db`
- Run migration:
```powershell
python run_mig.py
```
- Report output:
  - `data/migration_report_v2.json`

## Run App
```powershell
python main.py
```
or
```powershell
run_app.bat
```

## Validation
- Data migration:
  - check `migration_report_v2.json` counts and errors
- Functional checks:
  - home page shows product positioning, feature guide, and project structure
  - create anomaly requires problem description
  - close anomaly requires improvement description
  - create visit requires date + supplier plus at least one product section or visit-level defect note
  - visit records can aggregate multiple product sections and show defect-note counts / pending-improvement counts
  - anomaly with linked visit can open visit detail from event list
  - workflow tabs split visit records, visit-linked anomalies, standalone anomalies, and closed cases
  - monthly stats and Excel export match selected month
  - event PDF export includes visit defect notes and anomaly photo attachments when present
