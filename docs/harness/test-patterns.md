# Test and Harness Verification Patterns — SQE DailyWork

## Scope
This document consolidates detailed testing conventions, harness patterns, migration verification rules, and automated test guardrails for `SQE DailyWork`. Reference this document from `AGENTS.md` to keep rule files concise.

---

## 1. Migration and Harness Test Patterns

- **defect_supplier_id backfill tests**: `defect_supplier_id_backfill_v1` runs once at `create_schema` when `migration_meta` != `1`; test backfill success by inserting supplier+defect after first schema, deleting the meta key, then re-running `create_schema`; memory DB `defect_records` inserts need `defect_no, event_date, processing_line, item_no, qty, defect_desc, status, created_at`.
- **Harness membership**: After adding tracked source/tests, update `docs/harness/source-baseline-manifest.md` live count (`(git ls-files --cached --others --exclude-standard | Where-Object { Test-Path $_ }).Count`) before `harness_check.ps1` membership drift fails.
- **Verify Full runner coverage**: Full and Coverage `scripts/verify.ps1` use `Invoke-UnittestDiscoverWindowsSafe` (package-qualified `tests.<module>`; Full splits into 2 chunks, Coverage into 4 chunks at `test_event_list_widget_render_stability.py`), then `ncr.tests.test_core` + `ncr.tests.test_supplier_sync`, then pytest on `test_anomaly_folder_creation.py`, `test_attachment_rename.py`, `test_table_sorting.py`. Do not use bare `unittest discover -s tests` as Windows Full/Coverage evidence.
- **Disposable DB path assertions**: Under `SQE_DB_PATH`, `DATA_DIR` resolves to the override parent—not `PROJECT_ROOT / "data"`. Attachment/export path tests must assert against `app_paths.data_dir()`, not a hard-coded repo `data/` path.
- **NCR in-memory supplier-sync tests**: `create_defect` tests need `processing_line` (`原物料` / `委外加工`) and a stub shared `suppliers` table so `_sync_and_resolve_supplier_id` runs; `supplier_records` alone is insufficient without the shared-master gate table.
- **NCR export column assertions**: Excel detail asserts must track `DETAIL_EXPORT_COLUMNS` order (e.g. `processing_line` precedes `item_no`); do not keep stale cell letters from pre-export-layout schemas.
- **Visual baseline refresh contract**: Regenerate required baselines with the same verified disposable DB as verify (`scripts/sqlite_backup.py` formal->scratch, set `SQE_DB_PATH` + `SQE_REQUIRE_DISPOSABLE_DB=1`). Data-bound targets (`stats-stress`, charts) false-fail if refreshed against a different DB snapshot.
- **Build traceability**: `build_windows.ps1` calls `write_build_info.py --output <staging>/build-info.json`; it never rewrites tracked `src/build_info.py`. Distro metadata records git/toolchain/zip SHA-256; startup logs `build_label()`.
- **NCR create embedding smoke**: Assert `CreateWorkflowShell.content_scroll` hosts `NcrCreateFormContent` and that `fields_widget` lives in that subtree—never `content_scroll.widget() is fields_widget`.
- **Workflow smoke trace contract**: `scripts/smoke_test_v2.py` must set `anomaly_source` (e.g. `訪廠／稽核` when trace ERP patterns are unset) and must not expect `supplier_id IS NULL` products inside `list_active_products_for_supplier` (strict mode).
- **Exec-plan lifecycle**: Completed plans belong in `docs/exec-plans/completed/` only; `harness_check.ps1` fails if `active/` contains `Plan status: completed`.
- **VIEW / repeat-links migration guards**: VIEW readiness via `sqlite_master.sql` or COUNT, not `_table_exists`; `product_records` VIEW filters `is_active=1` (Promotion CLI); `refresh_repeat_links_for_suppliers` calls `require_repeat_links_schema` before write (symmetric with `list_repeat_issues`).

---

## 2. Refactoring & DRY Verification Rules

- **Trace & Keyword Simplification Pass**: When DRY-ing ERP trace / SMT keyword additions:
  - Loop `TRACE_FIELD_PATTERN_KEYS` / `TRACE_FIELD_LABELS` instead of hardcoding four field keys.
  - Reuse `_assert_trace_field_pattern` (validator), `_anomaly_write_fields` (anomaly CRUD), and `processing_line_source_hint` (NCR->異常 handoff).
  - Do not change locked `ValueError` copy (`ERP 格式規則`, `格式不符合`)—`tests/test_anomaly_trace_fields.py` asserts them.
  - Exclude from simplify passes: `anomaly_trace_contract`, migrations/repository schema, `list_column_contract`, `layout_constants`, paired stats pareto pipelines in `stats_view_widget`, and wiring `find_anomaly_trace_duplicate` unless explicitly requested.
  - Qt create-form submit tests must set `anomaly_source` before `_on_submit()` or mocks never fire.

---

## 3. PySide6 / Qt Automated Testing Guardrails

- **Automated Modal Guard**: Never invoke blocking `QMessageBox` / `QDialog.exec()` in `closeEvent`, `_ensure_has_active_suppliers`, or other automated handlers. Use `ui.runtime_mode.is_automated_runtime()` (`QT_QPA_PLATFORM == "offscreen"`, `SQE_TESTING`, `SQE_PROBE`, `SQE_REQUIRE_DISPOSABLE_DB`) and skip the prompt.
- **No `cls.app.quit()` in Test tearDownClass**: Never call `app.quit()` in test suite teardowns; doing so destroys the shared `QApplication` event loop for subsequent test suites.
- **Single Fusion Style Init**: Never call `setStyle("Fusion")` inside individual test `setUpClass` methods; initialize it once globally in `tests/__init__.py` to prevent Qt C++ style engine race conditions.
- **PySide6 eventFilter Return Contract**: In custom `eventFilter` implementations mounted on `QApplication`, unhandled events MUST `return False` directly; never invoke `return super().eventFilter(watched, event)` to prevent PySide6 C++ trampoline `RecursionError` hangs.
- **Targeted Widget Refresh over Deep Recursion**: Dynamic theme or preference changes must use `findChildren(TargetClass)` instead of deep-recursive layout activation across thousands of widgets.
- **CJK Font Resolution Cache**: Wrap OS font registry scans in `@lru_cache(maxsize=1)` to avoid multi-second startup and rendering stalls.
- **QShortcut Escape**: Use `QKeySequence(Qt.Key.Key_Escape)`—not `QKeySequence.StandardKey.Escape` (invalid in PySide6).
- **GlobalSearchDialog tests**: Dialog `parent` must be `QWidget`; stub routing with `QWidget` + mocked methods, not `MagicMock` as parent.
- **Full-page Qt tearDown**: Shared `QWidget` `_host` + tracked `_pages`; close tracked pages only—never `topLevelWidgets()` sweep (closes `_host`). No `mock.Mock()` parent; mock tab service calls. No `DeferredDelete` flush in same module (SEH).
- **CI unittest hang watchdog**: `tests/hang_watchdog.py` arms on `GITHUB_ACTIONS` or `SQE_TEST_HANG_SECONDS>0` (CI default 180s). Dump all-thread traceback and `os._exit(3)` instead of waiting for the job timeout. CI `verify.ps1` uses `PYTHONUNBUFFERED=1` and unittest `-v`. A cancelled job is not a green gate.

---

## 4. UI Visual Closure Gate

- **Trigger**: Any visible change under `src/ui/` (layout, cards, comparison panels, typography, CJK copy, QSS roles).
- **Required**: Native Windows `scripts/qt_visual_probe.py --target <mapped>` with `--min-width` and `--scale 1.0,1.25,1.5` when the surface is resizable; read the saved PNG (console CJK is cp950 display noise).
- **Pass JSON**: `visual_trustworthy: true`, `cjk_font_ok: true`, `qss_unknown_property_warnings: 0`, exit code `0`.
- **Widget → target** (see also `.claude/skills/sqe-dailywork-change-router/SKILL.md`):

| Surface | Target |
| --- | --- |
| `repeat_issues_management_page.py` | `repeat-issues-management` |
| `anomaly_management_page.py`, workbench tabs | `workbench` |
| `repeat_issues_panel.py` | `workbench` |
| `stats_view_widget.py` | `stats-stress` |
| `ncr_stats_widget.py` | `ncr-stats` |
| `event_list_widget.py` | `event-list` |
| `theme.py`, global QSS | touched targets or `qt_visual_belt.py` |

- **Offscreen unittest** (`QT_QPA_PLATFORM=offscreen`): structural smoke only — never visual evidence.
- **Delivery semantics**: Skipped mandatory probe → label **`not verified`** or keep task open. **Do not** write skipped probe under `Residual risk`. `Residual risk` is only for post-check environmental limits.
- **Table cell widget clipping**: `QTableWidget::setCellWidget` rows that host `QPushButton` must not use `variant="secondary"` (min-height 30 + padding + border exceeds fixed `setRowHeight`). Use `make_table_cell_action_button` (`role="tableCellAction"`) and `WORKBENCH_ACTION_ROW_HEIGHT` from `layout_constants.py`. Assert `rowHeight >= cellWidget.sizeHint().height()` in focused table tests; other `setCellWidget` tables may call `resizeRowToContents` after populate.
- **ActionItemListWidget row clipping**: per-row controls must use `ACTION_ITEM_ROW_MIN_HEIGHT` (`CONTROL_MIN_HEIGHT`), `ACTION_ITEM_ROW_V_MARGIN`, and `ACTION_ITEM_HEADER_GAP`; do not hardcode `setMinimumHeight(28)`. Validation uses `set_validation_invalid()` on empty description `QLineEdit` children—not `set_field_invalid()` on the list container.

Example:

```powershell
.venv\Scripts\python.exe scripts\qt_visual_probe.py --target repeat-issues-management --min-width --scale 1.0,1.25,1.5 --output Outputs\visual_qa\repeat-issues-management\probe.png
```
