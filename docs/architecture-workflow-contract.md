# SQE DailyWork Architecture Workflow Contract

## Purpose

This contract is the design checkpoint for every SQE DailyWork change. The app
is a single ERP-style desktop program with two daily workflow data lines and one
shared master-data area.

## Data Responsibility Matrix

| Area | Tables | Source | Writes Allowed From | Must Not Write |
| --- | --- | --- | --- | --- |
| Shared master data | `suppliers`, `products` | Company product and supplier master data | Manual master-data dialogs; ERP/Excel master import | Supplier events, visit/audit defect notes, warehouse defect records |
| Supplier event management | `visits`, `visit_product_sections`, `visit_defect_notes`, `anomalies` | Supplier visits, audits, and confirmed supplier abnormal events | Visit/audit dialogs; explicit supplier-anomaly conversion | `defect_records` |
| Warehouse physical nonconforming-product management | `defect_records` | Physical items in the nonconforming-product warehouse | Embedded warehouse tracker only | `visits`, `visit_defect_notes`, `anomalies` |
| Import audit | `import_batches`, `import_batch_rows` | ERP/Excel import runs | Import services | Workflow data rows |

## Flow Boundaries

1. Visit or audit defects are recorded first as lightweight
   `visit_defect_notes`.
2. A visit or audit defect becomes a formal supplier abnormal event only through
   an explicit confirmation path that writes `anomalies.visit_id`.
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

## Supplier Anomaly Quality-Report Requirement

- `anomalies.quality_report_required` is the nullable source of truth for
  「品質異常單要求」: `1` means 是, `0` means 否, and `NULL` means a legacy row
  that has not been classified. Schema upgrades add the column without
  backfilling or guessing historical values.
- `NewAnomalyDialog` requires an explicit 是／否 selection before a new or
  edited anomaly can be saved. Read-only preview preserves the stored state.
- Supplier-event Excel detail output is split by the authoritative
  `event_type`: `VISIT` rows go to `訪廠` and `ANOMALY` rows go to `異常`.
  The removed combined sheet `異常事件明細` must not be recreated by filtering
  or relabeling a mixed dataset. The `異常` sheet exports 是／否／未設定 for
  「品質異常單要求」; the visit sheet omits anomaly-only fields. This split
  supports downstream filtering without changing existing charts, summary
  totals, supplier ranking, or warehouse NCR reports.

## UI Entrypoint And Folder Boundaries

- The app has one daily desktop shell: `main.py` with `src/ui/main_window.py`.
- The sidebar grouping expresses workflow structure, not data ownership: three
  domain group headers (text labels) — 供應商事件, 倉庫不合格品, 系統 — organize
  首頁 (overview) plus the supplier-event scopes (單獨異常 / 訪廠發現異常 /
  訪廠紀錄 / 已結案) and 異常事件統計; 倉庫不合格品 holds 建立不合格品 /
  待處理委外加工 / 待處理原物料 / 歷史紀錄 / 不合格品統計分析; 系統 holds 基礎資料. The four
  supplier-event scopes are first-class sidebar rows (deep-linking into the single
  事件管理 page and setting its scope via `EventListWidget.set_event_scope`), not
  an in-page scope tab bar.
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
  project guidance belongs in `docs/`.
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
