# Embedded Warehouse Nonconforming-Product Module

This module provides the warehouse physical nonconforming-product workflow inside
the SQE DailyWork main window. It is not a standalone desktop app.

## Scope

- Tracks physical nonconforming items in the warehouse through `defect_records`.
- Keeps NCR-style record numbers and warehouse disposition fields.
- Provides embedded pages through `ncr/embed.py`.
- Uses the active shared SQLite database `data/sqe_v2.db`.

Supplier visit/audit defect notes are outside this module. They belong to
`visit_defect_notes` and may be confirmed into formal supplier anomalies, not
warehouse `defect_records`.

## Data

Primary workflow table:

- `defect_records`

Warehouse-module support tables:

- `ui_settings`
- `product_records` for warehouse item-name compatibility support
- `supplier_records` for legacy warehouse supplier-list compatibility support

Shared company master data lives in `suppliers/products`. Future ERP imports
should target the shared master tables unless the operation is explicitly a
warehouse compatibility import.

`ncr/db/database.py::initialize_database` is an embedded compatibility wrapper:
it opens the active `data/sqe_v2.db` connection and ensures the shared
repository schema exists. It is not a standalone `ncr/data/defect.db` migration
entrypoint. In-memory `apply_schema` remains available for focused warehouse
module unit tests.

## Import And Export

- Shared product/supplier import is handled by
  `services/master_import_service.py`.
- The retained `ncr/services/product_import_service.py` updates warehouse
  compatibility data and `defect_records.product_name`; label it as
  warehouse-scoped if surfaced in UI.
- Warehouse Excel export remains in `ncr/services/export_service.py`.

## Retired Standalone Shells

The former standalone NCR main window and product/supplier management UI shells
are retired. Keep verification focused on embedded use from root `main.py`.
Do not add a second NCR desktop launcher or multi-page NCR sidebar shell.

## Verification

Run the SQE DailyWork gate:

```powershell
.\scripts\verify.ps1
```

Focused module checks:

```powershell
python -m unittest ncr.tests.test_core ncr.tests.test_supplier_sync
python -m unittest tests.test_ncr_embedding_smoke
```
