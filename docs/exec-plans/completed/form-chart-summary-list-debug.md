# Form Chart Summary List Debug

## Goal

Audit and fix evidenced defects across SQE DailyWork form, chart, summary/dashboard,
and list-view surfaces while preserving existing data contracts.

## Decisions

- Use debug-fix mode because the request asks to find and fix problems.
- Treat supplier-event and warehouse NCR surfaces separately.
- Patch only defects reproduced by tests, probes, or direct code/data evidence.

## Progress

- Mapped form, chart, summary/dashboard, and list-view surfaces.
- Fixed monthly summary/KPI standalone-vs-visit count drift for legacy empty
  `visit_id` rows.
- Fixed stats dashboard error/empty branches so modified chart grids always
  activate/update and request repaint before returning.
- Added focused regression tests for the fixed paths.

## Verification

- `pytest` focused belt: 188 passed.
- `python -m compileall -q main.py src scripts tests`: passed.
- `scripts/harness_check.ps1`: passed.
- Native `scripts/qt_visual_probe.py` for `stats-stress` and `ncr-stats` at
  1.0/1.25/1.5 scale: passed with Windows Qt, CJK font OK, and no unknown QSS
  warnings.
- `scripts/verify.ps1` rerun with the repo virtualenv and a longer timeout:
  passed compileall, 391 unittest tests, offscreen UI smoke, native Qt visual
  probe, and `scripts/harness_check.ps1`.

## Remaining work

- None for this completed plan. Release membership is handled by the
  pre-production readiness gate.
