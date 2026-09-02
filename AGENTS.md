# Repository AGENTS.md — SQE DailyWork

## Scope
This file defines `SQE DailyWork` repo-local instructions. It serves as the
single source of truth and authoritative repository policy for all AI assistants
(including Cursor, Codex, Claude Code, and Gemini/Antigravity). It narrows the
global baseline for this single project; it does not replace or weaken the
global baseline.

## Knowledge Map
- Product and runtime overview: `README.md`.
- Architecture and data-boundary contract: `docs/architecture-workflow-contract.md`.
- UI layout and theme contract: `docs/ui-layout-theme-contract.md`.
- UI design framework (cross-project): `docs/SQE_Incident_Management_UI_Design_Framework_v0.1.md`.
- Cursor rules: `.cursor/rules/agents_gateway.mdc`.
- Active risks: `docs/risk-ledger.md`.
- Closed-loop harness: `docs/harness/README.md`, `docs/harness/closed-loop-log.md`, `docs/harness/quality-score.md`, and `docs/harness/doc-gardening.md`.
- Agent orchestration protocol (RACI, task tiering, routing, error-learning): `docs/harness/agent-orchestration.md`; cross-tool conflict log: `docs/harness/contradiction-log.md`.
- Claude Code automation: `docs/harness/claude-code-automation.md`, `.claude/settings.json`, `.claude/hooks/`, `.claude/skills/`, and `.claude/agents/`.
- AI rules compatibility and source-control boundary: `docs/harness/ai-rules-compatibility.md`, `docs/harness/source-baseline-manifest.md`, `.agents/rules/agents_gateway.md`, `.cursor/rules/agents_gateway.mdc`, `CLAUDE.md`, and `.codex/rules/project.rules`.
- Execution plans: `docs/exec-plans/active/` and `docs/exec-plans/completed/`.
- Data backup: `scripts/backup_data.ps1`.
- Verification gate: `scripts/verify.ps1`; harness structure check: `scripts/harness_check.ps1`.
- Native Qt visual probe: `scripts/qt_visual_probe.py`.
- Command policy: `.codex/rules/project.rules`.

## Local Guardrails
- Keep the app a single-user local PySide6 + SQLite Supplier Quality Engineering desktop tool.
- Preserve the workflow contracts in `README.md`: supplier anomaly create/close, warehouse nonconforming-product records, separated statistics, shared master lists, imports, exports, and report generation. Visit product UI is retired per `docs/exec-plans/completed/retire-visit-product-line.md`; legacy visit schema remains for existing data only.
- Preserve v2 data contracts and existing storage paths unless the user explicitly requests a contract change.
- Keep SQE DailyWork terminology aligned across services, dialogs, tables, `src/ui/popup_i18n.py`, and `README.md`.
- Keep `docs/architecture-workflow-contract.md` synchronized when changing workflow tables, import behavior, statistics, or entrypoint routing.
- Cursor rules live in `.cursor/rules/`; do not remove the rules directory.
- **Trunk-Based Development**：遵循全域 `CLAUDE.md` 的 TBD 規則，所有開發直接在 `main` 進行，禁止開 feature branch。

## 1. Core Architectural Laws (The Atomic Path)
Every core design change must be reflected across the entire stack. Never leave "ghost" fields or orphaned code.
1. **Data layer**: `src/database/` (connection, repository, migration).
2. **Service layer**: `src/services/` (business rules, Excel export).
3. **Desktop UI**: `src/ui/` — `main_window.py` routing, `src/ui/widgets/` pages, `src/ui/theme.py` (QSS), **`src/ui/layout_constants.py`** (single source of layout numbers; values pinned by `tests/test_layout_constants.py`).
4. **User-visible copy**: Prefer `src/ui/popup_i18n.py` for service messages; keep terminology consistent across dialogs and tables.

## 2. Business Process Rules
- **Two workflow data lines**: Supplier event management and warehouse physical nonconforming-product management are different sources and must not be merged in code, UI copy, reports, or statistics.
- **Shared master data**: `suppliers` and `products` are shared company master data and may be used by both workflow lines. Existing NCR compatibility tables such as `product_records` are warehouse-module support data, not the primary shared product master. Four fixed-scope master pages (`suppliers.category` = `原物料供應商` / `委外加工`; `products.item_category` = `原物料` / `半成品` / `成品`; `0`-prefix `product_code` → `原物料`); `PAGE_MASTER` → raw supplier.
- **Warehouse nonconforming products**: `defect_records` stores physical products in the nonconforming-product warehouse only. Do not write supplier visit/audit findings into `defect_records`.
- **Workflow split contract**: When a workflow or navigation item is split into separate user-facing flows, do not implement it by relabeling the same page, adding a hidden fixed filter, or inferring scope from incidental fields. Define and update the full contract in the same change: authoritative data source/field, route/page keys, sidebar active state, badge/count query, legacy-data handling, export/list/delete scope, tests, and docs. Compatibility aliases may remain only when explicitly marked compatibility-only and unused by new navigation.
- **Visit product line retirement**: Legacy `visits` / `visit_defect_notes` / `anomalies.visit_id` schema remains; product UI retired (no visit dialogs, scopes, stats, or exports). Anomaly create uses `sync_visit=False`; `PAGE_VISIT_CREATE` is compatibility-only. See `docs/exec-plans/completed/retire-visit-product-line.md`.
- **Closure (`anomalies.status`)**: Only `待處理` / `已結案`. Closing goes through `close_anomaly`: non-empty `improvement_desc` (改善說明) is required, and `closed_at` is set (normalized date; service/repository defaults apply). Do not refer to legacy names `verification_result` / `verified_at` in new code—they are not v2 columns.
- **Statistics boundary**: Supplier event statistics must query supplier event tables; warehouse nonconforming-product statistics must query `defect_records`. Do not combine these counts into a generic quality-abnormality metric unless the UI explicitly labels and separates both sources.
- **Import boundary**: Keep database import paths because future ERP imports will reduce manual entry. Imports that update shared master data must target `suppliers/products` with preview, backup, and reconciliation. Warehouse compatibility imports may update warehouse support tables only when clearly labeled as warehouse-module data.
- **Soft Delete**: Use `is_active: bool = True` for Models. Filter by `is_active=True` in all standard queries.
- **Temporal Standard**: Use ISO-8601 dates in services; UI shows localized Traditional Chinese where applicable.
- **Badge and List Count Alignment**: Event scope counts displayed inside the event query page must align exactly with each chip's `event_scope` filter. The sidebar `事件查詢` badge is an intentionally unscoped operational total of all open supplier anomalies; chip counts remain scope-specific. Supplier-event operational queue counts (`逾期案件`, `根因待查`, `處置項目`) display on the **作業佇列** page chips and must use `get_supplier_event_queue_counts` (COUNT=LIST); the sidebar 作業佇列 row has no badge. Warehouse badges remain constrained to `status <> '已結案' AND processing_line = <formal line>`.
- **Scope chip count SSOT**: Chip `(N)` labels must consume `_query_service.get_event_scope_counts()` or `repository.list_events(..., event_scope=<scope>)`—never per-scope ad-hoc COUNT SQL.
- **Global search NCR routing**: Warehouse hits from `search_global` route by `status` + `processing_line` (已結案→歷史、委外加工→待處理委外、原物料→待處理原物料、未分流→`open_warehouse_unclassified_pending`); never default all NCR hits to outsource pending.
- **Supplier 360 read model**: Supplier overview and supplier 360 pages aggregate `anomalies` and `defect_records` as separate source-labelled read-only projections. Legacy `visits` rows are not exposed in product UI. They must not merge statistics, exports, or writes across the supplier-event and warehouse lines.
- **NCR supplier linkage**: `defect_records.supplier_id` is a nullable FK to shared `suppliers.id`, backfilled only by exact supplier-name matches; unmatched legacy rows remain NULL. NCR create/update paths resolve `supplier_id` on save without merging warehouse records into supplier-event tables.
- **NCR-to-anomaly traceability**: Explicit user action `轉開供應商異常` records `anomalies.source_defect_no` from the originating warehouse defect number. It does not mutate or delete the warehouse record.
- **NCR→anomaly category handoff**: `convert_to_supplier_anomaly` pre-fills `category` only when NCR `category` is in `ANOMALY_CATEGORY_OPTIONS`; otherwise leave empty.
- **Anomaly lexicon SSOT**: `category` / `anomaly_source` must come from `ui_settings` presets (`supplier_event.anomaly_categories.v1`, `supplier_event.anomaly_sources.v1`); manage via **顯示設定 → 表單與業務**; `create_anomaly` / `update_anomaly` validate with `is_valid_category`.
- **Statistics Chart and List Category Alignment (including Dialogs)**: When updating statistics charts (e.g. Pareto chart), listings, reports, or management dialogs, ensure category display and category grouping remain strictly consistent across the system. The system uniformly consumes `category` ("異常類別") for all anomalies across dialogs, lists, Excel export detail tables, PDF exports, and Pareto charts. The page Pareto chart, the Excel export Pareto table, and the export-embedded chart PNG must all consume the single `get_anomaly_category_pareto_by_range` implementation.
- **SMT Process Keyword Statistics Boundary**: Supplier anomalies may store multi-value SMT process keywords in `anomalies.process_keywords` (newline-delimited). The SMT keyword Pareto chart, Excel keyword sheet, and export-embedded keyword PNG must all consume the single `get_anomaly_process_keyword_pareto_by_range` implementation. Do not merge SMT keywords into `category` or warehouse NCR statistics.
- **Supplier Event List Columns (Anomaly No over Date)**: For all supplier event lists (such as the EventListWidget query tabs and supplier-event queue pages), the first column must be named "異常單號" (Anomaly Number) instead of "日期" (Date).
- **Anomaly Number Format and Editing Constraints**: The anomaly number (`anomaly_no` or `ref_no`) is strictly restricted to exactly 11 digits of pure numbers (format: `YYYYMMDDNNN`). The first 8 digits must align with the selected date (e.g., date 2026/05/12 requires prefix 20260512). When the date edit value changes in the UI, the anomaly number must automatically regenerate to align with the new date. Manual edits to this number are allowed but must be validated on submit for uniqueness, length (11 digits), and date prefix alignment. In tests, mocks for anomaly number previews must conform to this valid 11-digit numeric schema matching the mock date.
- **Analysis note attachment count**: Live COUNT from `anomaly_attachments` by `related_note_id`; do not trust stored `anomaly_analysis_notes.attachment_count`.


## 3. UI/UX & Styling Standards (Slate + Electric Blue)
- **Terminology**: Keep labels and status terms consistent with existing dialogs and `src/ui/popup_i18n.py` patterns.
- **Grid Layout** (single source of truth: `src/ui/layout_constants.py`; values pinned by `tests/test_layout_constants.py` — import the constants, do not hardcode pixels):
  - Standard form area max width: `960px` (`FORM_MAX_WIDTH`, dialog `setMaximumWidth`).
  - Top-level page outer frame `PAGE_OUTER_MARGINS = (24, 24, 24, 24)`; main panel inner padding `PANEL_MARGINS = (12, 10, 12, 10)`.
  - 2-column grid rhythm: `GRID_GUTTER = 12`, `ROW_GAP = 8` for `QGridLayout`; `QFormLayout` uses `FORM_HORIZONTAL_SPACING = 16` / `FORM_VERTICAL_SPACING = 12`.
- **Aesthetics**: High density, light Slate surfaces, Electric Blue primary actions, card-based professional internal-tool look.
- **Workbench topology**: Keep default 事件查詢 operational, not decorative. No hero/cover panels, feature tours, card-in-card wrappers, or retired home hub.
- **Dashboard & Stats Refresh Standard**: Dashboard/statistics pages need manual「重新整理」(`variant="secondary"`, left of「匯出 Excel」); `MainWindow._switch_primary_page` must call `refresh_data()`; end refresh with `self.update()`; after `deleteLater()` + re-add widgets call `layout.activate()` and `layout.update()` on modified layouts.
- **ScrollArea ChartView Feedback Loop Prevention**: Interactive QtCharts in `QScrollArea` (`widgetResizable=True`) must use `StableChartView`, not raw `QChartView`, to avoid `sizeHint`/`sceneRect` height feedback loops; cap `sizeHint` at `minimumHeight`.
- **Chart Typography Hierarchy & Single Source of Truth**: All Qt charts consume `src/ui/widgets/chart_style.py` scale (`CHART_*_POINT_SIZE` tokens: title 11pt bold, axis title 9pt bold, labels 9pt, legend/data 8pt). Never hardcode ad-hoc `QFont` sizes; use `apply_chart_surface(chart)` and `apply_axis_typography(axis)`.
- **Bottom Action Bar Standard (方案 A 底部操作列)**: All full-page create and entry surfaces (`CreateWorkflowShell` / `DefectFormWidget`) must place primary action buttons at the bottom of the form (never in the top header). Layout order follows Scheme A: secondary/reset actions on the left (`清除 / 重置`), primary workflow actions on the right (`返回清單` + `儲存`).
- **Itemized Description Standard (條列式逐條審閱動線)**: Descriptions, defect findings, and tracking items must use the dynamic numbered row component `BulletListWidget` (`[序號] [輸入框] [刪除]` + `+ 新增條目`) to facilitate item-by-item review while maintaining newline-delimited text compatibility.
- **Zero-Noise Analytics Standard (統計看板純淨化)**: Statistics dashboards strictly retain only the Date Range filter, Refresh button, Export Excel button, and visual charts. Textual insight summaries and verbose diagnostic paragraphs must not be displayed on the visible UI. During `refresh_data()`, do not create, populate, or compute hidden insight, info-banner, or management-summary text; when simplifying statistics pages, remove the generation path and compatibility widgets—do not rely on `.hide()` alone.
- **CJK Radio Button Guard (單選與核取按鈕 CJK 排版守衛)**: Never invoke `setLayoutDirection(Qt.LayoutDirection.RightToLeft)` on `QRadioButton` or `QCheckBox` containing CJK text. Windows Qt calculates reverse bounding boxes that cause indicator circles to render directly on top of Chinese characters. Keep default `LeftToRight` and structure container layouts with adequate widths.
- **Table Column Width Single Source of Truth (表格欄位寬度單一真理標準)**: All `QTableWidget` columns must consume layout constants from `src/ui/layout_constants.py` (e.g. `CASE_QUEUE_*`, `NCR_LIST_CORE_*`, `EVENT_LIST_CORE_*`). Context-specific minimums are: case-queue Anomaly No `CASE_QUEUE_ANOMALY_NO_WIDTH = 106px`; event-list compact Anomaly No `EVENT_LIST_CORE_ANOMALY_NO_WIDTH = 106px`; NCR defect No `NCR_LIST_CORE_DEFECT_NO_WIDTH = 120px`. Other core business data remains Part No >= 130px, 7-char CJK headers >= 115px, Email >= 180px, and Phone >= 140px.
- **Symmetric Grid Layout Standard (雙欄表單網格對稱對齊標準)**: Multi-field forms must use symmetric 2-column grids (`field_count=2`: Col 0/2 for labels, Col 1/3 for fields with 1:1 stretch). Do not mix column offsets in a single grid layout. Accessory actions (such as '+ 建立' product buttons) must be packed inside the field container QHBoxLayout.
- **Feedback**: `QMessageBox` for confirmations; destructive actions use explicit confirm dialogs.
- **Export/UI display SSOT**: `list_column_contract` export cells must match page renderer strings (e.g. `overdue` → `逾期`/`—`); assert in `tests/test_exports_phase7.py`.
- **CaseStageStepper status rules**: Never use `bool()` on `root_cause_status`, `corrective_action_status`, or `verification_result`; defaults like `尚未開始`, `—`, `待驗證` are non-empty and falsely complete stages. Use explicit status checks in `CaseStageStepper.set_case_state`; `load_anomaly` must pass `get_overview_card()` overview.

## 4. Coding & Refactoring Standards
- **Desktop QSS**: Prefer QSS roles (`role`, `variant`) and theme tokens over ad-hoc per-widget `setStyleSheet`, except where already established (e.g. tech-transfer cards).
- **Rename before Delete**: When removing fields, rename them first (e.g., `status` -> `status_DELETING`) to let the compiler highlight all references.
- **Grep Search**: After changes, verify application directories (`src/database/`, `src/services/`, `src/ui/`) are clean of old terms.
- **Trace & Keyword Simplification Pass (行為不變精簡)**: When DRY-ing ERP trace / SMT keyword additions, loop `TRACE_FIELD_PATTERN_KEYS` / `TRACE_FIELD_LABELS` instead of hardcoding four field keys; reuse `_assert_trace_field_pattern` (validator), `_anomaly_write_fields` (anomaly CRUD), and `processing_line_source_hint` (NCR→異常 handoff). Do not change locked `ValueError` copy (`ERP 格式規則`, `格式不符合`)—`tests/test_anomaly_trace_fields.py` asserts them. Exclude from simplify passes: `anomaly_trace_contract`, migrations/repository schema, `list_column_contract`, `layout_constants`, paired stats pareto pipelines in `stats_view_widget`, and wiring `find_anomaly_trace_duplicate` unless explicitly requested. Qt create-form submit tests must set `anomaly_source` before `_on_submit()` or mocks never fire.
- **Workbench dialog enum SSOT**: Loop `ANOMALY_*_STATUSES` / `ANOMALY_EVIDENCE_TYPES` + `ANOMALY_EVIDENCE_LABELS` from `repo_helpers`; no local `EVIDENCE_OPTIONS` or identity-map dicts.
- **Startup Performance & Heavy Dependency Lazy Loading**:
  - **Heavy 3rd-party dependencies**: Heavy libraries (e.g. `openpyxl`, `reportlab`, `matplotlib`) must never be imported statically at module level in services or UI classes loaded during startup. Always import them inside the specific function or method where they are invoked.
  - **No module-level style instantiation**: Never instantiate style objects (e.g. `Font()`, `PatternFill()`, `Border()`) at the module root; encapsulate them in cached helper functions (e.g. `_get_export_styles()`).
  - **Module-level service imports for test mock compatibility**: In UI files, keep service module imports (e.g. `from ncr.services import export_service`) at module level while ensuring the service file itself lazy-loads heavy external packages. This preserves `unittest.mock.patch` target stability in tests while eliminating startup latency.
  - **Lazy full-page form shells**: Container pages that wrap full dialogs (such as `EventCreatePage`) must support `lazy_load=True` and defer child form creation to `_ensure_form_installed()` and `@property form` accessor on `showEvent`.
  - **Startup query deduplication**: Avoid redundant `refresh_data()` calls in `MainWindow._setup_ui` if the child widget's `__init__` already queries initial data.
- **PySide6 / Qt Automation & Anti-Deadlock Guardrails**:
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
- **Migration and harness test patterns**:
  - **defect_supplier_id backfill tests**: `defect_supplier_id_backfill_v1` runs once at `create_schema` when `migration_meta` ≠ `1`; test backfill success by inserting supplier+defect after first schema, deleting the meta key, then re-running `create_schema`; memory DB `defect_records` inserts need `defect_no, event_date, processing_line, item_no, qty, defect_desc, status, created_at`.
  - **Harness membership**: After adding tracked source/tests, update `docs/harness/source-baseline-manifest.md` live count (`(git ls-files --cached --others --exclude-standard | Where-Object { Test-Path $_ }).Count`) before `harness_check.ps1` membership drift fails.
  - **Verify Full runner coverage**: Full `scripts/verify.ps1` runs `unittest discover -s tests`, then `ncr.tests.test_core` + `ncr.tests.test_supplier_sync`, then pytest on `test_anomaly_folder_creation.py`, `test_attachment_rename.py`, `test_table_sorting.py`. Do not assume `unittest discover` alone covers NCR or pytest module-level tests.
  - **Disposable DB path assertions**: Under `SQE_DB_PATH`, `DATA_DIR` resolves to the override parent—not `PROJECT_ROOT / "data"`. Attachment/export path tests must assert against `app_paths.data_dir()`, not a hard-coded repo `data/` path.
  - **NCR in-memory supplier-sync tests**: `create_defect` tests need `processing_line` (`原物料` / `委外加工`) and a stub shared `suppliers` table so `_sync_and_resolve_supplier_id` runs; `supplier_records` alone is insufficient without the shared-master gate table.
  - **NCR export column assertions**: Excel detail asserts must track `DETAIL_EXPORT_COLUMNS` order (e.g. `processing_line` precedes `item_no`); do not keep stale cell letters from pre-export-layout schemas.
  - **Visual baseline refresh contract**: Regenerate required baselines with the same verified disposable DB as verify (`scripts/sqlite_backup.py` formal→scratch, set `SQE_DB_PATH` + `SQE_REQUIRE_DISPOSABLE_DB=1`). Data-bound targets (`stats-stress`, charts) false-fail if refreshed against a different DB snapshot.
  - **Build traceability**: `build_windows.ps1` calls `write_build_info.py --output <staging>/build-info.json`; it never rewrites tracked `src/build_info.py`. Distro metadata records git/toolchain/zip SHA-256; startup logs `build_label()`.
  - **NCR create embedding smoke**: Assert `CreateWorkflowShell.content_scroll` hosts `NcrCreateFormContent` and that `fields_widget` lives in that subtree—never `content_scroll.widget() is fields_widget`.
  - **Workflow smoke trace contract**: `scripts/smoke_test_v2.py` must set `anomaly_source` (e.g. `訪廠／稽核` when trace ERP patterns are unset) and must not expect `supplier_id IS NULL` products inside `list_active_products_for_supplier` (strict mode).
  - **Exec-plan lifecycle**: Completed plans belong in `docs/exec-plans/completed/` only; `harness_check.ps1` fails if `active/` contains `Plan status: completed`.
  - **VIEW / repeat-links migration guards**: VIEW readiness via `sqlite_master.sql` or COUNT, not `_table_exists`; `product_records` VIEW filters `is_active=1` (Promotion CLI); `refresh_repeat_links_for_suppliers` calls `require_repeat_links_schema` before write (symmetric with `list_repeat_issues`).


## 4.1 Design Framework Cross-Reference
Items 1-9 of `docs/SQE_Incident_Management_UI_Design_Framework_v0.1.md` §7.7 are implemented—see `docs/ui-layout-theme-contract.md` (do not duplicate helpers). Item 10 via `EVENT_LIST_CORE_*` / `NCR_LIST_CORE_*`; items 11-15 planning only.


## 5. AI Verification Guardrails (Evidence-First Protocol)
To ensure system stability and avoid "suspicion-based" errors, the following rules are mandatory:
1. **NO GUESS-WORK**: Never modify code based on a guess or "suspicion." You must use diagnostic tools to confirm the state before proposing a fix.
2. **THE "SUSPECT" TRIGGER**: If you find yourself using words like "suspect," "probably," or "likely," you are forbidden from proposing an edit until you have verified the root cause with evidence.
3. **ROOT CAUSE ANALYSIS (RCA)**: Every implementation plan must include an "RCA" section providing technical proof of why the change is necessary.
4. **LOGGING OVER GUESSING**: If you cannot find the root cause through static analysis, you must first propose adding diagnostic logs to capture runtime behavior before attempting a fix.

## Closed-loop Harness
- Use the completion impact format for task delivery: `Changes`, `Impact`, `Verification`, `Residual risk`, and `Next action`.
- For debugging, regressions, repeated failures, or Investigation Path work, add Debug/RCA fields: `Observed`, `Root cause`, `Fix`, `Harness update needed`, and `Destination`.
- If a harness update is needed, update the narrowest durable location: repo docs, tests, `scripts/verify.ps1`, `scripts/harness_check.ps1`, `.codex/rules/project.rules`, `.cursor/rules/agents_gateway.mdc`, or this file.
- If the final Debug/RCA status would be `Harness update needed: yes`, invoke the `/learn` workflow, or the current memory-update equivalent, before marking the task complete. Include the learn destination/result in the final delivery.
- Keep one-off bug details out of global Codex rules. Promote only reusable project knowledge into `docs/harness/closed-loop-log.md` or the relevant source-of-truth doc.
- For complex changes, create a short plan under `docs/exec-plans/active/` and move it to `docs/exec-plans/completed/` after completion.
- This format does not weaken global Hard Triggers, `blocked`, `not verified`, or `not pass` semantics.

## 7. Verification
- Small text/docs-only edits: focused inspection plus `scripts\harness_check.ps1` when harness files changed.
- Python code edits: use `scripts\verify.ps1` when practical; otherwise run the closest focused unittest or compile check and report the gap.
- UI behavior changes: use offscreen Qt only for structural smoke checks such as startup, widget existence, and signal wiring.
- UI visual review, screenshots, typography, and Chinese text rendering checks must use the native Windows Qt platform through `scripts\qt_visual_probe.py` or an equivalent native-platform capture. Do not treat `QT_QPA_PLATFORM=offscreen` screenshots as visual evidence because offscreen can miss Windows CJK fonts and render square glyphs.
- **qt_visual_probe multi-target**: One `--target` per invocation per `scripts/qt_probe_targets.json` (no `home`). Multiple flags execute only the last target.
- **Windows chunked unittest**: Full/Coverage use `Invoke-UnittestDiscoverWindowsSafe` (Coverage: 4 chunks); never single discover as Windows Coverage evidence; see §4 tearDown.
- **Coverage evidence chain**: `assert_coverage_baseline.py` alone ≠ `-Profile Coverage` PASS; require `scratch/verify-coverage-*-final*.log` with full chain + `EXIT:0` (see `docs/release/coverage-baseline.json`).
- **Button audit dual gate**: orchestrator exit `0`, no `orchestrator_status: FAILED`, no unregistered Worker/SEH pages; exit `1` with zero exceptions is not PASS.
- **Windows packaging gate**: Frozen writable roots use `src/app_paths.py`. Build in isolated staging with sanitized PATH; audit PyInstaller dependencies; promote to `dist/` only after bounded `--smoke-exit` creates a scratch DB and non-empty marker. Immediate windowed-exe return is not success; `-SkipSmoke` never promotes.
- **CI vs release gate**: CI Full/Coverage/Soak uses `-AllowSchemaOnlySource` + `-SkipNativeVisual`; CI green ≠ portable release-ready. Local cut: `-Profile Release` + Full with native visual on verified disposable DB (`docs/release/production-release-runbook.md`).
- **Release profile**: `verify.ps1 -Profile Release` runs harness → workflow smoke → button audit → build → portable smoke. Before gates it writes a fail-closed current summary and preserves the prior summary; `-UseExistingDist` skips rebuild. Promotion audit is read-only. Rollback-ready requires a previous verified zip whose SHA-256 matches its successful summary.
- **Release DB safety**: Use verified backup + disposable snapshots only; do not write `data/sqe_v2.db` during verify unless explicitly authorized.
- Data migration, destructive data changes, or export/data-contract changes follow the global Hard Trigger rules and require explicit verification evidence.

## 8. Multi-Assistant Coexistence
- **Coexistence Policy:** Codex, Claude Code, Cursor, and Gemini/Antigravity operate in the same workspace. All assistants must treat this file as the authoritative repository policy. Cursor rules are defined in `.cursor/rules/` and point to this file. **Trunk-Based Development (TBD)** 為所有 AI 工具的強制開發流程：一律直接提交到 `main`，禁止開 feature branch。
- **Gemini (Antigravity) Flow & Workflow Sync:** When operating via Antigravity, strictly follow `~/.gemini/GEMINI.md` triage (L0/L1/M1/F1/F2), implementation plans, and the Gate A~F checklists. Deliverables (plans, tasks, walkthroughs) must use Traditional Chinese (繁體中文). If changes were directly made using Cursor or Claude Code without prior Gemini plan approval, the developer must perform `git diff` when switching back to Gemini, manually update `walkthrough.md` to document changes, and resolve any process gaps before completing the task.
- **Command Policy & Codex Sync Rule:** Any modifications or additions to verification and development commands must be synchronized with the Python-like rules in `.codex/rules/project.rules` to prevent Codex sandbox blocks.
- **AI Rules Compatibility:** Read `docs/harness/ai-rules-compatibility.md` before cross-tool handoff or governance edits. Official claims, local observations, audit inferences, assumptions, and `not verified` items must remain labeled.
- **Source-Control Boundary:** If `git status --short` is noisy, the source baseline is absent, or the repo was just initialized, use one writer per worktree. Do not run parallel writing AI tools in the same checkout. Prefer Antigravity New Worktree Mode for complex or parallel tasks; Local Mode is for small interactive work only.
- **Agent Orchestration:** For non-trivial coding tasks, follow `docs/harness/agent-orchestration.md` — Claude defines spec / architecture / risk, Codex implements / tests / diff, Gemini/Antigravity verifies with native Qt evidence, Cursor handles light in-editor edits. Task tiering (L0 / Standard / Heavy) is bound to the existing Hard Triggers; review findings use P0–P3 severity; the human-approval gate reuses the existing pre-tool hook and Codex rules rather than a new mechanism; and cross-tool rule conflicts go to `docs/harness/contradiction-log.md` for a user decision. This does not replace this file as the single source of truth.
