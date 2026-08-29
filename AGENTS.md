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
- Preserve the workflow contracts in `README.md`: supplier event create/close, visit or audit create/complete, warehouse nonconforming-product records, separated statistics, shared master lists, imports, exports, and report generation.
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
- **Shared master data**: `suppliers` and `products` are shared company master data and may be used by both workflow lines. Existing NCR compatibility tables such as `product_records` are warehouse-module support data, not the primary shared product master.
- **Warehouse nonconforming products**: `defect_records` stores physical products in the nonconforming-product warehouse only. Do not write supplier visit/audit findings into `defect_records`.
- **Workflow split contract**: When a workflow or navigation item is split into separate user-facing flows, do not implement it by relabeling the same page, adding a hidden fixed filter, or inferring scope from incidental fields. Define and update the full contract in the same change: authoritative data source/field, route/page keys, sidebar active state, badge/count query, legacy-data handling, export/list/delete scope, tests, and docs. Compatibility aliases may remain only when explicitly marked compatibility-only and unused by new navigation.
- **Legacy visit defect notes**: `visit_defect_notes` remains a supported supplier-event table for existing data (`缺失內容` required, `改善內容` / `備註` optional) and explicit conversion to a formal anomaly preserves `visit_id`. The current `NewVisitDialog` does not expose a defect-note entry control; do not reintroduce a separate `登錄訪廠缺失` entry point or infer new notes from warehouse records. Preserve legacy notes and product sections when editing a visit.
- **Anomaly ↔ Visit link (`anomalies.visit_id`)**: The schema allows `NULL` for legacy, tests, or when the user turns off visit sync. Product-default behavior (e.g. `defect_form_widget`「同步建立訪廠紀錄」checked): call `create_anomaly_with_visit_link` with `sync_visit=True` so the system reuses a same-day visit or creates one and stores `visit_id`. Use `sync_visit=False` or `create_anomaly` without `visit_id` only when intentionally omitting a visit link.
- **Closure (`anomalies.status`)**: Only `待處理` / `已結案`. Closing goes through `close_anomaly`: non-empty `improvement_desc` (改善說明) is required, and `closed_at` is set (normalized date; service/repository defaults apply). Do not refer to legacy names `verification_result` / `verified_at` in new code—they are not v2 columns.
- **Statistics boundary**: Supplier event statistics must query supplier event tables; warehouse nonconforming-product statistics must query `defect_records`. Do not combine these counts into a generic quality-abnormality metric unless the UI explicitly labels and separates both sources.
- **Import boundary**: Keep database import paths because future ERP imports will reduce manual entry. Imports that update shared master data must target `suppliers/products` with preview, backup, and reconciliation. Warehouse compatibility imports may update warehouse support tables only when clearly labeled as warehouse-module data.
- **Soft Delete**: Use `is_active: bool = True` for Models. Filter by `is_active=True` in all standard queries.
- **Temporal Standard**: Use ISO-8601 dates in services; UI shows localized Traditional Chinese where applicable.
- **Badge and List Count Alignment**: Event scope counts displayed inside the event-management page must align exactly with each chip's `event_scope` filter. The sidebar `事件管理` badge is an intentionally unscoped operational total of all open supplier anomalies; chip counts remain scope-specific. Warehouse badges remain constrained to `status <> '已結案' AND processing_line = <formal line>`.
- **Scope chip count SSOT**: Chip `(N)` labels must consume `_query_service.get_event_scope_counts()` or `repository.list_events(..., event_scope=<scope>)`—never per-scope ad-hoc COUNT SQL.
- **Global search NCR routing**: Warehouse hits from `search_global` route by `status` + `processing_line` (已結案→歷史、委外加工→待處理委外、原物料→待處理原物料、未分流→`open_warehouse_unclassified_pending`); never default all NCR hits to outsource pending.
- **Event create prefill symmetry**: `open_new_anomaly_create_page` and `open_new_visit_create_page` both accept `initial_data`; `EventCreatePage` visit branch must pass `initial_data` into `NewVisitDialog`.
- **Supplier 360 read model**: Supplier overview and supplier 360 pages aggregate `anomalies`, `visits`, and `defect_records` as separate source-labelled read-only projections. They must not merge statistics, exports, or writes across the supplier-event and warehouse lines.
- **NCR supplier linkage**: `defect_records.supplier_id` is a nullable FK to shared `suppliers.id`, backfilled only by exact supplier-name matches; unmatched legacy rows remain NULL. NCR create/update paths resolve `supplier_id` on save without merging warehouse records into supplier-event tables.
- **NCR-to-anomaly traceability**: Explicit user action `轉開供應商異常` records `anomalies.source_defect_no` from the originating warehouse defect number. It does not mutate or delete the warehouse record.
- **NCR→anomaly category handoff**: `convert_to_supplier_anomaly` pre-fills `category` only when NCR `category` is in `ANOMALY_CATEGORY_OPTIONS`; otherwise leave empty.
- **Statistics Chart and List Category Alignment (including Dialogs)**: When updating statistics charts (e.g. Pareto chart), listings, reports, or management dialogs, ensure category display and category grouping remain strictly consistent across the system. The system uniformly consumes `category` ("異常類別") for all anomalies across dialogs, lists, Excel export detail tables, PDF exports, and Pareto charts. The page Pareto chart, the Excel export Pareto table, and the export-embedded chart PNG must all consume the single `get_anomaly_category_pareto_by_range` implementation.
- **SMT Process Keyword Statistics Boundary**: Supplier anomalies may store multi-value SMT process keywords in `anomalies.process_keywords` (newline-delimited). The SMT keyword Pareto chart, Excel keyword sheet, and export-embedded keyword PNG must all consume the single `get_anomaly_process_keyword_pareto_by_range` implementation. Do not merge SMT keywords into `category` or warehouse NCR statistics.
- **Supplier Event List Columns (Anomaly No over Date)**: For all supplier event lists (such as the EventListWidget query tabs and the HomeWidget backlog table), the first column must be named "異常單號" (Anomaly Number) instead of "日期" (Date). The row rendering must show the `ref_no` (anomaly number) if present, and fallback to `event_date` (date) only for visit records that lack an anomaly number. When sorting by this column, if the `ref_no` is empty (e.g., visits), the system must fallback to sorting by `event_date` to ensure stable sorting.
- **Anomaly Number Format and Editing Constraints**: The anomaly number (`anomaly_no` or `ref_no`) is strictly restricted to exactly 11 digits of pure numbers (format: `YYYYMMDDNNN`). The first 8 digits must align with the selected date (e.g., date 2026/05/12 requires prefix 20260512). When the date edit value changes in the UI, the anomaly number must automatically regenerate to align with the new date. Manual edits to this number are allowed but must be validated on submit for uniqueness, length (11 digits), and date prefix alignment. In tests, mocks for anomaly number previews must conform to this valid 11-digit numeric schema matching the mock date.


## 3. UI/UX & Styling Standards (Slate + Electric Blue)
- **Terminology**: Keep labels and status terms consistent with existing dialogs and `src/ui/popup_i18n.py` patterns.
- **Grid Layout** (single source of truth: `src/ui/layout_constants.py`; values pinned by `tests/test_layout_constants.py` — import the constants, do not hardcode pixels):
  - Standard form area max width: `960px` (`FORM_MAX_WIDTH`, dialog `setMaximumWidth`).
  - Top-level page outer frame `PAGE_OUTER_MARGINS = (24, 24, 24, 24)`; main panel inner padding `PANEL_MARGINS = (12, 10, 12, 10)`.
  - 2-column grid rhythm: `GRID_GUTTER = 12`, `ROW_GAP = 8` for `QGridLayout`; `QFormLayout` uses `FORM_HORIZONTAL_SPACING = 16` / `FORM_VERTICAL_SPACING = 12`.
- **Aesthetics**: High density, light Slate surfaces, Electric Blue primary actions, card-based professional internal-tool look.
- **Workbench topology**: Keep the first screen operational, not decorative. Do not reintroduce hero/cover panels, feature tours, project-structure copy, or card-in-card wrappers for the home workbench.
- **Dashboard & Stats Refresh Standard**: For any dashboard or analytical statistics pages (where underlying database records can be modified by other management tabs), always provide a manual "重新整理" button (styled as `variant="secondary"` and positioned to the left of the primary "匯出 Excel" button). Additionally, when switching to these statistics pages in `MainWindow._switch_primary_page`, always force a call to `refresh_data()` to ensure visual charts are up-to-date, bypassing any one-off lazy loading flags. To guarantee that the updated data is rendered immediately on the screen without layout freezes or visual lag, always invoke standard Qt update functions like `self.update()` at the end of the rendering/refresh methods. Additionally, when dynamically clearing widgets (e.g., using `deleteLater()`) and adding new widgets in a layout, you MUST call `layout.activate()` and `layout.update()` on all modified layouts to force Qt to recalculate geometry, preventing new widgets from collapsing to zero size.
- **ScrollArea ChartView Feedback Loop Prevention**: When placing any interactive QtCharts (`QChartView` or subclass inherited from `QGraphicsView`) inside a `QScrollArea` with `widgetResizable=True`, you MUST use `StableChartView` instead of raw `QChartView`. This prevents the infinite height increment feedback loop caused by `QGraphicsView`'s `sizeHint` tracking `sceneRect` (which expands as the view resizes, causing `QScrollArea` to continuously demand more height on every relayout). Keep `StableChartView`'s `sizeHint` capped at `minimumHeight` to let `QGridLayout` stretch weights properly govern height allocation.
- **Chart Typography Hierarchy & Single Source of Truth**: All Qt charts (supplier event statistics & warehouse NCR statistics) must strictly adhere to the compact high-density chart typography scale defined in `src/ui/widgets/chart_style.py`:
  - Chart Title: `11pt Bold` (`CHART_TITLE_POINT_SIZE`)
  - Axis Title: `9pt Bold` (`CHART_AXIS_TITLE_POINT_SIZE`)
  - Axis Labels (categories & tick values): `9pt Regular` (`CHART_AXIS_LABEL_POINT_SIZE`)
  - Legend Labels: `8pt Regular` (`CHART_LEGEND_POINT_SIZE`)
  - Data / Series / Point / Slice Labels: `8pt Regular / Bold` (`CHART_DATA_LABEL_POINT_SIZE`)
  Never hardcode ad-hoc `QFont` point sizes in chart builders; always consume `apply_chart_surface(chart)` and `apply_axis_typography(axis)`.
- **Bottom Action Bar Standard (方案 A 底部操作列)**: All full-page create and entry surfaces (`CreateWorkflowShell` / `DefectFormWidget`) must place primary action buttons at the bottom of the form (never in the top header). Layout order follows Scheme A: secondary/reset actions on the left (`清除 / 重置`), primary workflow actions on the right (`返回清單` + `儲存`).
- **Itemized Description Standard (條列式逐條審閱動線)**: Descriptions, defect findings, and tracking items must use the dynamic numbered row component `BulletListWidget` (`[序號] [輸入框] [刪除]` + `+ 新增條目`) to facilitate item-by-item review while maintaining newline-delimited text compatibility.
- **Zero-Noise Analytics Standard (統計看板純淨化)**: Statistics dashboards strictly retain only the Date Range filter, Refresh button, Export Excel button, and visual charts. Textual insight summaries and verbose diagnostic paragraphs must not be displayed on the visible UI. During `refresh_data()`, do not create, populate, or compute hidden insight, info-banner, or management-summary text; when simplifying statistics pages, remove the generation path and compatibility widgets—do not rely on `.hide()` alone.
- **CJK Radio Button Guard (單選與核取按鈕 CJK 排版守衛)**: Never invoke `setLayoutDirection(Qt.LayoutDirection.RightToLeft)` on `QRadioButton` or `QCheckBox` containing CJK text. Windows Qt calculates reverse bounding boxes that cause indicator circles to render directly on top of Chinese characters. Keep default `LeftToRight` and structure container layouts with adequate widths.
- **Table Column Width Single Source of Truth (表格欄位寬度單一真理標準)**: All `QTableWidget` columns must consume layout constants from `src/ui/layout_constants.py` (e.g. `HOME_BACKLOG_*`, `NCR_LIST_CORE_*`, `EVENT_LIST_CORE_*`). Context-specific minimums are: Home backlog Anomaly No `HOME_BACKLOG_ANOMALY_NO_WIDTH = 120px`; event-list compact Anomaly No `EVENT_LIST_CORE_ANOMALY_NO_WIDTH = 106px`; NCR defect No `NCR_LIST_CORE_DEFECT_NO_WIDTH = 120px`. Other core business data remains Part No >= 130px, 7-char CJK headers >= 115px, Email >= 180px, and Phone >= 140px.
- **Symmetric Grid Layout Standard (雙欄表單網格對稱對齊標準)**: Multi-field forms must use symmetric 2-column grids (`field_count=2`: Col 0/2 for labels, Col 1/3 for fields with 1:1 stretch). Do not mix column offsets in a single grid layout. Accessory actions (such as '+ 建立' product buttons) must be packed inside the field container QHBoxLayout.
- **Feedback**: `QMessageBox` for confirmations; destructive actions use explicit confirm dialogs.
- **CaseStageStepper status rules**: Never use `bool()` on `root_cause_status`, `corrective_action_status`, or `verification_result`; defaults like `尚未開始`, `—`, `待驗證` are non-empty and falsely complete stages. Use explicit status checks in `CaseStageStepper.set_case_state`; `load_anomaly` must pass `get_overview_card()` overview.

## 4. Coding & Refactoring Standards
- **Desktop QSS**: Prefer QSS roles (`role`, `variant`) and theme tokens over ad-hoc per-widget `setStyleSheet`, except where already established (e.g. tech-transfer cards).
- **Rename before Delete**: When removing fields, rename them first (e.g., `status` -> `status_DELETING`) to let the compiler highlight all references.
- **Grep Search**: After changes, verify application directories (`src/database/`, `src/services/`, `src/ui/`) are clean of old terms.
- **Trace & Keyword Simplification Pass (行為不變精簡)**: When DRY-ing ERP trace / SMT keyword additions, loop `TRACE_FIELD_PATTERN_KEYS` / `TRACE_FIELD_LABELS` instead of hardcoding four field keys; reuse `_assert_trace_field_pattern` (validator), `_anomaly_write_fields` (anomaly CRUD), and `processing_line_source_hint` (NCR→異常 handoff). Do not change locked `ValueError` copy (`ERP 格式規則`, `格式不符合`)—`tests/test_anomaly_trace_fields.py` asserts them. Exclude from simplify passes: `anomaly_trace_contract`, migrations/repository schema, `list_column_contract`, `layout_constants`, paired stats pareto pipelines in `stats_view_widget`, and wiring `find_anomaly_trace_duplicate` unless explicitly requested. Qt create-form submit tests must set `anomaly_source` before `_on_submit()` or mocks never fire.
- **Startup Performance & Heavy Dependency Lazy Loading**:
  - **Heavy 3rd-party dependencies**: Heavy libraries (e.g. `openpyxl`, `reportlab`, `matplotlib`) must never be imported statically at module level in services or UI classes loaded during startup. Always import them inside the specific function or method where they are invoked.
  - **No module-level style instantiation**: Never instantiate style objects (e.g. `Font()`, `PatternFill()`, `Border()`) at the module root; encapsulate them in cached helper functions (e.g. `_get_export_styles()`).
  - **Module-level service imports for test mock compatibility**: In UI files, keep service module imports (e.g. `from ncr.services import export_service`) at module level while ensuring the service file itself lazy-loads heavy external packages. This preserves `unittest.mock.patch` target stability in tests while eliminating startup latency.
  - **Lazy full-page form shells**: Container pages that wrap full dialogs (such as `EventCreatePage`) must support `lazy_load=True` and defer child form creation to `_ensure_form_installed()` and `@property form` accessor on `showEvent`.
  - **Startup query deduplication**: Avoid redundant `refresh_data()` calls in `MainWindow._setup_ui` if the child widget's `__init__` already queries initial data.
- **PySide6 / Qt Automation & Anti-Deadlock Guardrails**:
  - **Automated Modal Guard**: Never invoke blocking modal dialogs (`QMessageBox.question`, `QDialog.exec()`) unconditionally in `closeEvent` or automated handlers. Always check automated flags (`QT_QPA_PLATFORM == "offscreen"`, `SQE_TESTING`, `SQE_PROBE`, `SQE_REQUIRE_DISPOSABLE_DB`) and bypass interactive prompts in automated/probe runs.
  - **No `cls.app.quit()` in Test tearDownClass**: Never call `app.quit()` in test suite teardowns; doing so destroys the shared `QApplication` event loop for subsequent test suites.
  - **Single Fusion Style Init**: Never call `setStyle("Fusion")` inside individual test `setUpClass` methods; initialize it once globally in `tests/__init__.py` to prevent Qt C++ style engine race conditions.
  - **PySide6 eventFilter Return Contract**: In custom `eventFilter` implementations mounted on `QApplication`, unhandled events MUST `return False` directly; never invoke `return super().eventFilter(watched, event)` to prevent PySide6 C++ trampoline `RecursionError` hangs.
  - **Targeted Widget Refresh over Deep Recursion**: Dynamic theme or preference changes must use `findChildren(TargetClass)` instead of deep-recursive layout activation across thousands of widgets.
  - **CJK Font Resolution Cache**: Wrap OS font registry scans in `@lru_cache(maxsize=1)` to avoid multi-second startup and rendering stalls.
  - **QShortcut Escape**: Use `QKeySequence(Qt.Key.Key_Escape)`—not `QKeySequence.StandardKey.Escape` (invalid in PySide6).
  - **GlobalSearchDialog tests**: Dialog `parent` must be `QWidget`; stub routing with `QWidget` + mocked methods, not `MagicMock` as parent.
  - **Full-page Qt tearDown**: Close all `topLevelWidgets()` then `processEvents()`; no `sendPostedEvents(DeferredDelete)` in same module (SEH). `findChildren(PageClass)` insufficient.
- **Migration and harness test patterns**:
  - **defect_supplier_id backfill tests**: `defect_supplier_id_backfill_v1` runs once at `create_schema` when `migration_meta` ≠ `1`; test backfill success by inserting supplier+defect after first schema, deleting the meta key, then re-running `create_schema`; memory DB `defect_records` inserts need `defect_no, event_date, processing_line, item_no, qty, defect_desc, status, created_at`.
  - **Harness membership**: After adding tracked source/tests, update `docs/harness/source-baseline-manifest.md` live count (`(git ls-files --cached --others --exclude-standard | Where-Object { Test-Path $_ }).Count`) before `harness_check.ps1` membership drift fails.
  - **Verify Full runner coverage**: Full `scripts/verify.ps1` runs `unittest discover -s tests`, then `ncr.tests.test_core` + `ncr.tests.test_supplier_sync`, then pytest on `test_anomaly_folder_creation.py`, `test_attachment_rename.py`, `test_table_sorting.py`. Do not assume `unittest discover` alone covers NCR or pytest module-level tests.
  - **Disposable DB path assertions**: Under `SQE_DB_PATH`, `DATA_DIR` resolves to the override parent—not `PROJECT_ROOT / "data"`. Attachment/export path tests must assert against `app_paths.data_dir()`, not a hard-coded repo `data/` path.
  - **NCR in-memory supplier-sync tests**: `create_defect` tests need `processing_line` (`原物料` / `委外加工`) and a stub shared `suppliers` table so `_sync_and_resolve_supplier_id` runs; `supplier_records` alone is insufficient without the shared-master gate table.
  - **NCR export column assertions**: Excel detail asserts must track `DETAIL_EXPORT_COLUMNS` order (e.g. `processing_line` precedes `item_no`); do not keep stale cell letters from pre-export-layout schemas.
  - **Visual baseline refresh contract**: Regenerate required baselines with the same verified disposable DB as verify (`scripts/sqlite_backup.py` formal→scratch, set `SQE_DB_PATH` + `SQE_REQUIRE_DISPOSABLE_DB=1`). Data-bound targets (`stats-stress`, charts) false-fail if refreshed against a different DB snapshot.
  - **Build traceability**: Run `scripts/write_build_info.py` before `scripts/build_windows.ps1`; frozen distro ships `build-info.json` beside exe; startup log includes `build_label()` (git SHA + UTC timestamp + dirty flag).
  - **NCR create embedding smoke**: Assert `CreateWorkflowShell.content_scroll` hosts `NcrCreateFormContent` and that `fields_widget` lives in that subtree—never `content_scroll.widget() is fields_widget`.
  - **Workflow smoke trace contract**: `scripts/smoke_test_v2.py` must set `anomaly_source` (e.g. `訪廠／稽核` when trace ERP patterns are unset) and must not expect `supplier_id IS NULL` products inside `list_active_products_for_supplier` (strict mode).
  - **Exec-plan lifecycle**: Completed plans belong in `docs/exec-plans/completed/` only; `harness_check.ps1` fails if `active/` contains `Plan status: completed`.


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
- **qt_visual_probe multi-target**: Run one `--target` per invocation (`main`, `supplier-360`, `event-list`, `home`, `manager-view`); do not assume multiple `--target` flags execute all pages.
- **Windows unittest discover**: chunked runner at `test_event_list_widget_render_stability`; see §4 PySide6 tearDown.
- **Windows packaging gate**: Writable runtime roots (`data/`, `Outputs/`, `logs/`) resolve through `src/app_paths.py` (`runtime_root()` beside exe in frozen onedir). Build with `scripts\build_windows.ps1` (runs `write_build_info.py` first); validate frozen bundles with `SQE_DailyWork.exe --smoke-exit` on a scratch `SQE_DB_PATH` using `Start-Process -Wait` and `logs/smoke_exit.ok`—never treat immediate PowerShell return from a windowed exe as success.
- **CI release gate**: `.github/workflows/verify.yml` runs Full + `Coverage` + `Soak` verify jobs on push/PR; Full evidence `scratch/verify-full-log-final.txt`.
- **Phase 3 QA gates**: see `docs/exec-plans/completed/2026-08-22-qa-improvement-phase3.md` (`Coverage` / `Soak` profiles, portable smoke, release docs).
- **Release DB safety**: Production release validation uses verified backup + disposable snapshots only; do not write `data/sqe_v2.db` during verify unless the user explicitly authorizes live migration.
- Data migration, destructive data changes, or export/data-contract changes follow the global Hard Trigger rules and require explicit verification evidence.

## 8. Multi-Assistant Coexistence
- **Coexistence Policy:** Codex, Claude Code, Cursor, and Gemini/Antigravity operate in the same workspace. All assistants must treat this file as the authoritative repository policy. Cursor rules are defined in `.cursor/rules/` and point to this file. **Trunk-Based Development (TBD)** 為所有 AI 工具的強制開發流程：一律直接提交到 `main`，禁止開 feature branch。
- **Gemini (Antigravity) Flow & Workflow Sync:** When operating via Antigravity, strictly follow `~/.gemini/GEMINI.md` triage (L0/L1/M1/F1/F2), implementation plans, and the Gate A~F checklists. Deliverables (plans, tasks, walkthroughs) must use Traditional Chinese (繁體中文). If changes were directly made using Cursor or Claude Code without prior Gemini plan approval, the developer must perform `git diff` when switching back to Gemini, manually update `walkthrough.md` to document changes, and resolve any process gaps before completing the task.
- **Command Policy & Codex Sync Rule:** Any modifications or additions to verification and development commands must be synchronized with the Python-like rules in `.codex/rules/project.rules` to prevent Codex sandbox blocks.
- **AI Rules Compatibility:** Read `docs/harness/ai-rules-compatibility.md` before cross-tool handoff or governance edits. Official claims, local observations, audit inferences, assumptions, and `not verified` items must remain labeled.
- **Source-Control Boundary:** If `git status --short` is noisy, the source baseline is absent, or the repo was just initialized, use one writer per worktree. Do not run parallel writing AI tools in the same checkout. Prefer Antigravity New Worktree Mode for complex or parallel tasks; Local Mode is for small interactive work only.
- **Agent Orchestration:** For non-trivial coding tasks, follow `docs/harness/agent-orchestration.md` — Claude defines spec / architecture / risk, Codex implements / tests / diff, Gemini/Antigravity verifies with native Qt evidence, Cursor handles light in-editor edits. Task tiering (L0 / Standard / Heavy) is bound to the existing Hard Triggers; review findings use P0–P3 severity; the human-approval gate reuses the existing pre-tool hook and Codex rules rather than a new mechanism; and cross-tool rule conflicts go to `docs/harness/contradiction-log.md` for a user decision. This does not replace this file as the single source of truth.
