# Changelog

All notable changes to **SQE DailyWork** are documented here.
The version is the single source of truth in `src/app_version.py` (`__version__`)
and is shown in the main-window title bar and the startup log (`logs/app.log`).

Format follows [Keep a Changelog](https://keepachangelog.com/); this project
uses semantic versioning (MAJOR.MINOR.PATCH).

## [1.1.0] - 2026-08-22

Operational release with supplier-oriented UI closeout, frozen path contract, and
Windows onedir packaging.

### Added
- Supplier-oriented workbench: scope chips, Ctrl+K global search, supplier 360,
  case stepper, quarterly supplier report export, and NCR `supplier_id` linkage.
- `src/app_paths.py` as the single source for writable runtime roots in source
  and PyInstaller frozen builds.
- Windows distribution tooling: `scripts/sqe_dailywork.spec` and
  `scripts/build_windows.ps1` (onedir + portable zip).
- `main.py --smoke-exit` for automated frozen-bundle smoke checks.

### Fixed
- NCR create embedding smoke test aligned with `NcrCreateFormContent` wrapper DOM.
- `scripts/smoke_test_v2.py` aligned with strict supplier product scoping and
  anomaly trace-source requirements.

### Changed
- Version marker bumped to `1.1.0` in the window title and startup log.

## [1.0.0] - 2026-07-04

First production release of the single-user local PySide6 + SQLite Supplier
Quality Engineering desktop tool.

### Added
- Application version marker: `src/app_version.py` (`__version__ = "1.0.0"`),
  surfaced in the window title (`SQE DailyWork v1.0.0 - SQE 工作台`) and logged
  at startup so a build is identifiable from a bug report / log file.

### Fixed
- Audit timestamps (`created_at` / `updated_at`) now use local wall-clock time
  instead of UTC, so they no longer show the previous day for UTC+8 users near
  midnight. Date-range statistics are unaffected (they key off the date-only
  `anomaly_date` / `closed_at` values).
- `SQE_DB_PATH` override now also aligns the derived data directory and legacy
  database path, so the override's parent directory is created correctly on
  first run.

### Housekeeping
- Removed dead Genspark integration files and stopped tracking development/session artifacts
  (`.omo/`, `artifacts/visual/*.png`, root probe screenshots, diff dumps) from
  version control.
