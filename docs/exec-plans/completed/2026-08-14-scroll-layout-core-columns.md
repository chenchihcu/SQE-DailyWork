# 001#卷軸排版與核心欄位模式改版

Plan status: completed

## Done state

- `AppearancePreferencesDialog` uses finite pages instead of a whole-dialog scroll body.
- Supplier-event and NCR lists expose a compact core-column view at constrained widths and a reversible full-column view.
- UI display choices do not alter saved NCR column preferences, exports, data contracts, or unbounded-content scroll guards.

## Verification gates

- Focused UI/unit tests cover compact/full switching, persistence preservation, and dialog actions.
- Native Windows Qt probes cover `appearance-settings`, `event-list`, and `ncr-tracker` at 1.0/1.25/1.5 scale.
- `scripts/verify.ps1` is run when command policy permits; generated visual baselines are refreshed only after review.
