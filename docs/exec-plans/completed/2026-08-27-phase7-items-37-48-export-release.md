# Phase 7 項目 37–48 對照（Design-Derived）

Plan status: completed — design-derived export/report parity + release 1.2.0 for 48-item rollout Phase 7

## Scope and methodology

- `mapping_type`: **design-derived**
- Original 37–48 titles were never committed to the repository.
- Derived from architecture workflow export parity, Phase 3 deferred hypothesis PNG,
  Phase 6 manager view, supplier 360 report, and production release gates.
- **No schema / Promotion** in Phase 7.

## Item map

| # | derived_title | status |
| --- | --- | --- |
| 37 | Excel anomaly sheet SSOT append columns | complete |
| 38 | Event PDF quality conclusion + hypothesis embed | complete |
| 39 | Markdown snapshot overview parity | complete |
| 40 | Hypothesis tree PNG renderer + Excel sheet | complete |
| 41 | Manager view Excel export + UI button | complete |
| 42 | Supplier report repeat flag + overview columns | complete |
| 43 | Weekly PPTX overdue from overview SSOT | complete |
| 44 | `export_include_charts` gates chart/hypothesis PNG | complete |
| 45 | Focused export regression tests | complete |
| 46 | `verify_exports_phase7.ps1` + Full verify | complete |
| 47 | Docs / harness / Codex PHASE7 allow | complete |
| 48 | Version 1.2.0 + Windows onedir release (unsigned) | complete |

## Phase 7 evidence

- Date: 2026-08-27
- Focused: `scripts/verify_exports_phase7.ps1` (12 tests)
- Version: `src/app_version.py` → 1.2.0
- No formal DB Promotion (export-only)
