# Remove visit-create UI and product visit INSERT

Plan status: completed

## Goal

Remove every product path that creates a new visit (`visits` INSERT): sidebar
「新增訪廠」, event-list toolbar, Supplier 360 「安排訪廠」, `EventCreatePage`
visit branch, and anomaly 「同步建立訪廠紀錄」. Keep existing visit query,
edit/preview, schema, and test `create_visit()` helpers.

## Decisions

- Compact the QStackedWidget (no new ghost slot). `ANOMALY_CREATE_PAGE_INDEX =
  MASTER_PAGE_INDEX + 1`.
- `PAGE_VISIT_CREATE` remains compatibility-only and is unused by navigation.
- Product `create_anomaly_with_visit_link` defaults `sync_visit=False`.
  Explicit `visit_id` may still link an existing visit.
- Preference JSON still stores `default_sync_visit` / visit type / time slot;
  the appearance dialog no longer exposes create-visit controls. New default
  for `default_sync_visit` is `False`.
- Keep `NewVisitDialog` for edit/preview. Form-density probe captures that
  dialog (create-mode title may still read 「新增訪廠」); it is not a product
  navigation entry.

> **Superseded (2026-09-02):** `retire-visit-product-line` fully removed
> `NewVisitDialog` and visit product UI surfaces. Edit/preview visit dialog is
> no longer part of the product; legacy schema rows remain queryable only via
> data layer.

## Changes

- Sidebar, event-list toolbar, and Supplier 360 no longer offer visit-create.
- `EventCreatePage` only installs `kind="anomaly"`; `kind="visit"` raises
  `ValueError`.
- `NewAnomalyDialog` always sends `sync_visit=False`; repository/service
  defaults match.
- Appearance dialog dropped visit-create defaults; JSON fields retained.
- Probe/audit/baselines: removed `event-create-visit`; form-density visit
  capture uses `NewVisitDialog()`.

## Verification

- Focused unittest: 94 tests / 1 layout assertion fix then pass; appearance
  dialog, supplier 360, form-inline, and transaction-boundary tests pass.
- `scripts/harness_check.ps1` pass (live membership `689`).
- Native `qt_visual_probe.py` (`visual_trustworthy: true`) for `event-create`,
  `main`, `form-density`, `supplier-360`.
- Visual baselines refreshed at 1.0 / 1.25 / 1.5 for `form-density`,
  `event-create`, `appearance-settings`, `main`, `supplier-360`, `event-list`.
