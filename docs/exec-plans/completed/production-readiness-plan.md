# Production Readiness Plan — SQE DailyWork

## Scope
25-item remediation plan across 4 waves to address hidden bugs, data safety risks,
testing gaps, UX fool-proofing, and technical debt before production deployment.

---

## Wave 1: P0 Critical (Crash Safety + Data Integrity)

| # | Item | Files | Status |
|---|------|-------|--------|
| 1.1 | GUI popup on DB init failure | `main.py:91-96` | |
| 1.2 | WAL mode + busy timeout | `connection.py:get_connection()` | |
| 1.3 | Fix partial migration recovery | `migration.py` | |
| 1.4 | Add python-pptx to requirements | `requirements.txt` | |
| 1.5 | Add exception logging across all except blocks | All files with `except Exception` | |

### 1.1 GUI popup on DB init failure
- In `main.py` `except Exception` block of `initialize_database()`, create `QApplication`
  if not already, show `QMessageBox.critical` with Chinese message, then exit.
- **Why**: Silent exit code 1 on corrupted DB shows nothing when launched from shortcut.

### 1.2 WAL mode + busy timeout
- In `connection.py:get_connection()`, after `PRAGMA foreign_keys=ON`, add:
  - `conn.execute("PRAGMA journal_mode=WAL")`
  - `conn.execute("PRAGMA busy_timeout=5000")`
- **Why**: Two connections (main + NCR) to same DB risk `database is locked` errors.

### 1.3 Partial migration recovery
- Wrap suppliers + anomalies + visits migration in single `BEGIN IMMEDIATE ... COMMIT`.
- Alternatively: Track each sub-step in `migration_meta` for granular resume.
- **Why**: Crash after suppliers-commit but before anomalies-commit leaves inconsistent data.

### 1.4 Missing dependency
- Add `python-pptx>=1.0.0` to `requirements.txt`.

### 1.5 Exception logging
- Every `except Exception` block that shows a user dialog must also call
  `logger.exception(...)` before the dialog. Add module-level `logger = logging.getLogger(__name__)`.

---

## Wave 2: Transaction & Backup Integrity (P1)

| # | Item | Files | Status |
|---|------|-------|--------|
| 2.1 | Fix missing conn.commit() | `event_service.py` | |
| 2.2 | Confirmation dialogs | `defect_form_widget.py` | |
| 2.3 | Coverage tracking | `.coveragerc`, `verify.ps1`, `requirements.txt` | |
| 2.4 | Backup attachments | `backup_data.ps1` | |
| 2.5 | Backup integrity + rotation | `backup_data.ps1` | |

---

## Wave 3: UX Hardening + Monolith Split (P2)

| # | Item | Files | Status |
|---|------|-------|--------|
| 3.1 | Reject future anomaly dates | `defect_form_widget.py` | |
| 3.2 | Standardize RequiredFieldLabel | `defect_form_widget.py` | |
| 3.3 | Inline field validation | `defect_form_widget.py` | |
| 3.4 | Decompose repository.py | `src/database/` (8 new files) | |
| 3.5 | Case-insensitive supplier match | `master_import_service.py` | |

---

## Wave 4: Polish (P2-P3)

| # | Item | Files | Status |
|---|------|-------|--------|
| 4.1 | Eliminate dual defect_records schema | `ncr/db/database.py` | |
| 4.2 | aboutToQuit cleanup handler | `main_window.py` | |
| 4.3 | Migration script tests | `tests/test_migration_scripts.py` | |
| 4.4 | Global conftest.py | `tests/conftest.py` | |
| 4.5 | Remove PDF exporter global cache | `event_pdf_exporter.py` | |
| 4.6 | Configurable YIMED_SUPPLIER_NAME | `stats_service.py` | |

---

## Verification

After every wave:
```powershell
.\scripts\verify.ps1
```
Covers: compile check, unittest (325 tests), offscreen UI smoke, native Qt visual probe, harness structure.
