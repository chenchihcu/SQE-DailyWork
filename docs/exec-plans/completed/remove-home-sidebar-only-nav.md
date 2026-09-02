# Remove Home Hub — Sidebar-Only Navigation

Plan status: completed

## Goal

Retire the home workbench hub and sidebar `首頁` row; keep stack index `0` as a ghost
placeholder (no NCR reindex). Default startup opens **事件管理** (`events`).

## Changes

- `MainWindow`: `RetiredHomePlaceholder` at index `0`; removed `HomeWidget`; startup
  fallback and legacy `"home"` preference map to `EVENT_PAGE_INDEX`; `PAGE_HOME`
  redirects to events; sidebar badge refresh only.
- `SidebarNav`: removed `首頁` nav row; initial active `PAGE_EVENT_QUERY`.
- Deleted `src/ui/widgets/home_widget.py` and home-only tests.
- `AppearancePreferences`: default `events`; `"home"` migrates on load; dialog removes
  home radio.
- `qt_visual_probe --target home` deprecated alias → `event-list` (later removed; use
  `event-list` or `main`).
- Docs: README, architecture §UI entrypoint, ui-layout-theme-contract, CHANGELOG,
  visual QA checklist, change-router skill.

## Phase 2 cleanup (orphan baselines + dead code)

- Deleted `tests/visual_baseline/home/`; removed unreachable `_capture_home_window`
  from `qt_visual_probe.py`; added `Require-NoOrphanVisualBaselines` in
  `harness_check.ps1`.

## Verification

```powershell
$env:PYTHONPATH='src;.'
$env:QT_QPA_PLATFORM='offscreen'
.venv\Scripts\python.exe -m unittest `
  tests.test_top_nav_compact_height `
  tests.test_appearance_preferences_navigation `
  tests.test_appearance_preferences_dialog `
  tests.test_appearance_preferences `
  tests.test_layout_edge_alignment `
  tests.test_surface_usage_structure `
  tests.test_lightweight_visit_entry_routing `
  tests.test_stability_smoke `
  tests.test_ncr_embedding_smoke

powershell -NoProfile -ExecutionPolicy Bypass -File scripts/harness_check.ps1
```
