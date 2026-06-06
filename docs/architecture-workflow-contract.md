# SQETOOL Architecture Workflow Contract

## Purpose

This contract is the design checkpoint for every SQETOOL change. The app is a
single ERP-style desktop program with two daily workflow data lines and one
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

## UI Entrypoint And Folder Boundaries

- The app has one daily desktop shell: `main.py` with `src/ui/main_window.py`.
- The sidebar grouping expresses workflow structure, not data ownership:
  overview, supplier events, analysis/query, master data, and warehouse. Groups
  are conveyed by per-item icons and spacing (no text section headers); the
  logical groups, item order, and page indexes stay stable.
- Sidebar page indexes and stack routing must stay stable when labels, groups,
  or visual treatment change.
- Warehouse nonconforming-product tracking stays under the single embedded
  `src/ncr/` workflow page. Do not add a second root launcher or duplicate
  warehouse shell pages.
- Supplier and warehouse sidebar badges are read-only status indicators. They
  must not create cross-line writes or merge supplier-event and warehouse
  statistics.
- Runtime data, generated reports, and visual/debug artifacts stay in `data/`,
  `Outputs/`, `scratch/`, or the ignored root runtime `ncr/data/`; durable
  project guidance belongs in `docs/`.
- New source folders require a clear owner that is not already covered by
  `src/ui/`, `src/services/`, `src/database/`, `src/ncr/`, `scripts/`, or `tests/`.

## Statistics Boundary

- Supplier event statistics query supplier-event tables and must be labeled as
  supplier-event analysis.
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
- folder placement matches the owning workflow or documentation index
- focused tests cover the affected boundary
- `scripts/verify.ps1` passes for SQETOOL changes
- root `scripts/verify_all.ps1` passes when launchers, root scripts, or
  cross-workspace governance are touched
