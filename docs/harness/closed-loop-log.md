# Closed-loop Log

Use this file for reusable lessons from debugging, regressions, repeated failures, or Investigation Path work.

## Entry Template

```text
Date:
Task:
Changes:
Impact:
Verification:
Residual risk:
Next action:
Debug/RCA (when applicable):
Observed:
Root cause:
Fix:
Harness update needed:
Destination:
```

## Initial Entry

Date: 2026-05-16
Task: Install closed-loop harness.
Changes: Added root `AGENTS.md`, repo harness docs, exec-plan directories, a harness structure check, and a full verification entrypoint.
Impact: SQE DailyWork now has a single repo-local knowledge map while preserving tool-specific gateway files as adapters.
Verification: Run `scripts\harness_check.ps1` and `scripts\verify.ps1`.
Residual risk: full verification may still expose unrelated existing test/runtime debt; do not weaken the gate.
Next action: Use weekly harness gardening to report drift, then remediate only when explicitly requested.
Debug/RCA (when applicable):
Observed: The repo already had project command rules, tests, and smoke helpers, but no root `AGENTS.md` or canonical verification script.
Root cause: Repo-local guidance and verification existed in separate places without a single agent knowledge map.
Fix: Add repo `AGENTS.md`, harness docs, exec-plan directories, a harness structure check, and a full verification script.
Harness update needed: yes
Destination: `AGENTS.md`, `docs/harness/`, `docs/exec-plans/`, `scripts/harness_check.ps1`, `scripts/verify.ps1`, `.codex/rules/project.rules`

## Qt Visual Evidence Entry

Date: 2026-05-18
Task: Stop repeated false UI findings from Qt offscreen CJK rendering.
Changes: Added a native Qt visual probe and documented that offscreen Qt is structural-only evidence.
Impact: Future homepage and desktop UI reviews must use native Windows Qt screenshots before judging Chinese text rendering or typography.
Verification: Run `scripts\qt_visual_probe.py`; run `scripts\harness_check.ps1`.
Residual risk: native visual capture still depends on the local Windows desktop and installed fonts.
Next action: Use offscreen only for startup/widget smoke checks; use native capture for visual review.
Debug/RCA (when applicable):
Observed: Offscreen screenshots rendered Chinese text as square glyphs even though the Windows Qt platform displayed the same UI correctly.
Root cause: Qt offscreen on this host does not reliably load the Windows CJK font set used by the app.
Fix: Add `scripts/qt_visual_probe.py`, update repo guidance, and make the harness check require the native visual evidence rule.
Harness update needed: yes
Destination: `AGENTS.md`, `docs/harness/README.md`, `docs/harness/closed-loop-log.md`, `scripts/qt_visual_probe.py`, `scripts/harness_check.ps1`, `.codex/rules/project.rules`

## SQE DailyWork Integration Boundary Entry

Date: 2026-06-03
Task: Retire legacy NCR shells while preserving separated workflow data lines.
Changes: Added the architecture workflow contract; made shared master imports record batch/row audit data; converted visit defect notes to supplier anomalies only through explicit confirmation; kept warehouse statistics on `defect_records`; updated UI/UX docs and embedded NCR compatibility tests.
Impact: Future changes must treat supplier event management and warehouse physical nonconforming-product management as separate sources, with shared `suppliers/products` imports audited through `import_batches/import_batch_rows`.
Verification: Run `scripts\verify.ps1`, focused workflow tests, stale-term searches, and `scripts\qt_visual_probe.py`.
Residual risk: legacy references may remain in historical completed exec-plan documents only; active code/docs should not reintroduce standalone NCR launch or `ncr/data/defect.db` initialization.
Next action: Keep import and statistics changes tied to `docs/architecture-workflow-contract.md` and focused boundary tests.
Debug/RCA (when applicable):
Observed: NCR had been embedded, but old standalone DB initialization tests and stale multi-page sidebar comments still protected retired behavior.
Root cause: Prior integration removed the visible launcher path without making data-boundary, import-boundary, statistics-boundary, and verification contracts durable.
Fix: Promote the two-line workflow contract into docs, tests, compatibility wrappers, and UI/UX verification.
Harness update needed: yes
Destination: `AGENTS.md`, `README.md`, `docs/architecture-workflow-contract.md`, `docs/ui-layout-theme-contract.md`, `src/ncr/README.md`, focused unittest coverage

## Qt UI Removal And Compatibility Widgets Entry

Date: 2026-07-01
Task: Reduce repeated UI cleanup regressions after statistics dashboard fixes.
Changes: Added repo guidance for UI removal semantics, compatibility-only Qt widgets, and visual probe routing; updated relevant reusable Qt and chart UI skills.
Impact: Future PySide6 UI cleanup should remove unwanted cards/tabs from the real layout/object tree, catch parented-but-unmanaged dummy widgets, and avoid visual probes that toggle hidden compatibility proxies.
Verification: Run `scripts\harness_check.ps1`; run focused grep/diff checks for the new guidance.
Residual risk: Existing unrelated dirty UI files remain in the worktree; this entry only governs future implementation behavior.
Next action: Apply the same removal semantics when cleaning any remaining compatibility widgets.
Debug/RCA (when applicable):
Observed: A compatibility `QTabWidget` floated at the top-left because it was parented but not laid out or hidden; decision-summary cards were first hidden before the user clarified they should be removed.
Root cause: Existing guidance required native visual checks but did not explicitly audit parented-but-unmanaged Qt widgets or distinguish "hidden for compatibility" from "removed per user request".
Fix: Promote removal semantics and compatibility-widget scans into repo harness docs/rules and reusable Qt skill guidance.
Harness update needed: yes
Destination: `AGENTS.md`, `docs/harness/README.md`, `docs/harness/closed-loop-log.md`, `qt-desktop-layout-theme`, `spc-chart-ui`

## Badge Count Alignment Entry

Date: 2026-07-02
Task: Fix sidebar event badge count mismatch with displayed list count.
Changes: Updated `repository.get_dashboard_summary` to include `standalone_open_count` and modified `MainWindow._refresh_sidebar_badge` to use it for the "單獨異常" badge.
Impact: The "單獨異常" sidebar badge now displays the count of open standalone anomalies (6), matching the list of 6 items on the right side, instead of all open anomalies (11).
Verification: Run `pytest tests/test_event_manage_actions.py` (which includes `test_get_dashboard_summary_with_standalone_open_count`) and `pytest`.
Residual risk: None.
Next action: None.
Debug/RCA (when applicable):
Observed: The left sidebar badge for "單獨異常" displayed 11, while the right side displayed "共 6 筆".
Root cause: The sidebar badge was updated with `open_count` from `get_dashboard_summary`, which counted all open anomalies (standalone + visit-derived), whereas the right-side list only showed standalone anomalies.
Fix: Add `standalone_open_count` to the dashboard summary query and use it in the sidebar badge.
Harness update needed: yes
Destination: `AGENTS.md`, `docs/harness/closed-loop-log.md`, `tests/test_event_manage_actions.py`

## Anomaly Category Data Alignment Entry

Date: 2026-07-03
Task: Align legacy anomaly category names to standard UI dropdown options.
Changes: Added `align_legacy_anomaly_categories(conn)` in `repository.py`, integrated it into `initialize_database()` in `connection.py`, and added `tests/test_align_legacy_categories.py`.
Impact: Legacy category values in the database (such as '文件/SOP 不足') are automatically corrected to standard names on database initialization, resolving the discrepancy where legacy categories appeared in Pareto charts but were missing from UI dropdown options.
Verification: Run `pytest tests/test_align_legacy_categories.py` and `scripts\verify.ps1`.
Residual risk: None.
Next action: None.
Debug/RCA (when applicable):
Observed: The Pareto chart displayed "文件/SOP 不足" (with 2 items), but this option was absent in the anomaly category dropdown list in the UI form.
Root cause: The live database had legacy data containing "文件/SOP 不足", "人為操作疏失", "物料/來料問題", etc., in `root_cause_category` and `category` fields, which were not migrated when UI dropdown options were renamed.
Fix: Perform automated idempotent updates on database initialization to map all legacy names to current standard names.
Harness update needed: yes
Destination: `AGENTS.md`, `docs/harness/closed-loop-log.md`, `tests/test_align_legacy_categories.py`

## Category Alignment in Dialog and List Entry

Date: 2026-07-03
Task: Align event list category and anomaly dialog category for closed anomalies.
Changes: Added a read-only "原因分類" (cause category) field to `NewAnomalyDialog` when status is "已結案". Made the main "異常類別" combobox always display the raw category (`category_raw`) in both edit and read-only preview modes, aligning it with lists and preventing data overrides.
Impact: Avoids visual mismatches where the event list shows the resolved category (e.g. "其他") but the form shows the raw category (e.g. "包裝防護不足"). Also prevents saving from overwriting the raw category with the root cause category.
Verification: Run `tests/test_anomaly_category_dropdown.py` (including updated test cases) and `scripts/verify.ps1`.
Residual risk: None.
Next action: None.
Debug/RCA (when applicable):
Observed: Event lists and read-only previews showed resolved category while the edit form showed raw category, causing mismatches.
Root cause: Read-only preview loaded category (resolved), edit form loaded category_raw (raw), and `NewAnomalyDialog` had no field to display the `root_cause_category`.
Fix: Add a read-only `root_cause_display` field to `NewAnomalyDialog` for closed cases, and make both modes load `category_raw` for `category_input`.
Harness update needed: yes
Destination: `AGENTS.md`, `docs/harness/closed-loop-log.md`, `tests/test_anomaly_category_dropdown.py`

Date: 2026-07-04
Task: Align user-selected anomaly closure dates with event lists and trend charts.
Changes: Added a `結案日期` date picker to `CloseAnomalyDialog`, added a closed-date adjustment action for already closed anomalies, exposed `結案日期` in supplier-event anomaly lists, and documented that `anomalies.closed_at` is the single source for closure-date statistics.
Impact: Users can choose and later correct the closure date without reopening an anomaly; event-list preview, monthly cache, and the supplier-event trend chart now share the same `closed_at` source.
Verification: `pytest tests/test_event_manage_actions.py tests/test_anomaly_trend_by_range.py tests/test_event_list_widget_render_stability.py tests/test_event_action_menu_consistency.py tests/test_anomaly_category_dropdown.py -q` passed; `pytest tests/test_stats_view_anomaly_chart.py tests/test_form_field_pairing_layout.py tests/test_form_inline_validation_and_dirty.py -q` passed; `python -m compileall -q main.py src scripts tests` passed; read-only DB parity probe passed; `scripts/qt_visual_probe.py --target stats-stress` passed; `scripts/verify.ps1` timed out after 5 minutes.
Residual risk: Full repo gate completion remains unverified because `scripts/verify.ps1` timed out.
Next action: Re-run `scripts/verify.ps1` with a longer external timeout before release if full-gate evidence is required.
Debug/RCA (when applicable):
Observed: The trend chart grouped closed counts by `closed_at`, but the close dialog did not expose a user-selectable closure date and event lists did not preview the field.
Root cause: `repository.close_anomaly()` supported `closed_at`, while `CloseAnomalyDialog` and `event_service.close_anomaly()` omitted it and relied on repository defaulting.
Fix: Pass user-selected `closed_at` through the close path, add a closed-date-only adjustment path, and add list/chart/documentation parity checks.
Harness update needed: no
Destination: `tests/test_event_manage_actions.py`, `tests/test_anomaly_trend_by_range.py`, `tests/test_event_list_widget_render_stability.py`, `tests/test_anomaly_category_dropdown.py`, `docs/harness/closed-loop-log.md`

## Hidden-Error Production Closeout Entry

Date: 2026-07-14
Task: Repair confirmed hidden P1/P2 defects without running migration or tests on the formal database.
Changes: Replaced raw WAL copies with verified SQLite online backup; isolated verification/probes behind `SQE_DB_PATH`; made anomaly/cache and legacy migration boundaries atomic; converted post-commit snapshot failure to a recoverable warning; centralized repository invariants; separated import/report semantics; and made native target/baseline plus repository-membership drift executable gates.
Impact: A failed cache update cannot leave a reported-failed committed anomaly, snapshot failure no longer invites duplicate retry, migration cannot silently complete after row loss, cross-supplier links and invalid anomaly numbers are rejected below the UI, partial chart exports disclose missing charts, and Full verification covers every required Windows Qt target at 100/125/150% DPI.
Verification: `scripts/verify.ps1 -Profile Focused` passed; full unittest passed 434 tests in 901.780 seconds; offscreen structural smoke, definite-error Ruff, compileall, native 28-check Windows Qt visual belt at 100/125/150%, all nine required pixel-regression targets, harness, and `git diff --check` passed. Formal DB read-only integrity/count parity passed at 14 tables and 246 rows; business rows match the Phase 0 snapshot.
Residual risk: One live supplier/product ownership row is `VERIFY`; it is exported for user classification and is never auto-modified. Phase 0 and closeout raw DB hashes differ only through two older `monthly_stats_cache.updated_at` values in the closeout source; the cause is not uniquely provable, so no live restore or cache write was performed.
Next action: Classify the `VERIFY` row in a separate controlled data-correction task; do not combine it with this code closeout.
Debug/RCA (when applicable):
Observed: Existing tests and harness could pass while raw backup omitted WAL data, formal DB initialization remained reachable, row-level migration errors wrote completion metadata, themed form overflow was order-dependent, and visual probes/baselines no longer described the same surfaces.
Root cause: Authoritative DB mutations, derived outputs, verification data paths, and governance manifests had independent boundaries without executable parity checks.
Fix: Make the SQLite transaction or verified snapshot the authoritative boundary; downgrade only post-commit derived-output failures to explicit warnings; route repeated defects into focused tests and machine-readable manifests; compare the harness against live Git membership and real baseline files.
Harness update needed: yes
Destination: `tests/test_database_backup.py`, `tests/test_database_isolation.py`, `tests/test_anomaly_transaction_boundaries.py`, `tests/test_migration_atomicity.py`, `scripts/verify.ps1`, `scripts/harness_check.ps1`, `scripts/qt_probe_targets.json`, `docs/harness/source-baseline-manifest.md`, `docs/harness/closed-loop-log.md`

## Warehouse (NCR) Visual-Consistency Entry

Date: 2026-07-24
Task: Align warehouse nonconforming-product (NCR) page colors/element design with the supplier-event side, per user report that the two workflow lines look inconsistent.
Changes: Fixed `src/ncr/ui/ui_style.py` helpers (`create_section_card`, `create_section_title_with_icon` → `create_section_title`, `add_labeled_field`, `make_notice_label`, `make_hint_label`) to set the QSS-matched `role` property instead of a never-matched `uiRole` property, and to reuse existing shared roles (`panel`, `sectionTitle`, `helperText`, `messageText`) instead of NCR-only names with no QSS rule; removed all OS-native `QStyle.StandardPixmap` button/section icons (`apply_button_icon`, `ICON_PIXMAP_NAMES`, `standard_icon` deleted as dead code); fixed a hard-coded `AlignRight` field-label override back to left-aligned; split `defect_list.py`'s single unstyled card into a `role="subpanel"` filter/action panel plus a `role="panel"` results panel (mirroring `defect_list_widget.py`); replaced its plain-text empty-result label with the shared `EmptyStateWidget`; added missing bold section headers (基礎資訊/處理狀態) to `defect_form.py`; added a `role="separator"` divider rule and a `tone="success"` `messageText` variant to `src/ui/_qss_base.py`; mirrored `QWidget#StatsView`'s explicit `page_bg` rule for `QWidget#NcrStatsView` in `src/ui/_qss_tabs.py`; removed dead `dialog.setStyleSheet(ncr_app_stylesheet())` (already a no-op) from `main_window.py`.
Impact: Warehouse create/edit forms, the three list/tracking pages, and the warehouse stats dashboard now render with the same card framing, button styling (no OS icons), section-title typography, field-label alignment, and page background as the supplier-event pages, without changing any shared token values (colors were never actually divergent — only the property key was wrong, so the QSS rules silently never matched).
Verification: Native Windows Qt screenshots via `scripts\qt_visual_probe.py --target ncr-tracker|ncr-stats|event-list|stats-stress` before/after; focused unittest run (69 tests: `test_ncr_defect_form_*`, `test_ncr_defect_list_edit_dialog`, `test_ncr_embedding_smoke`, `test_ncr_stats_grid_dashboard`, `test_ncr_unclassified_hint`, `test_layout_constants`, `test_theme_*`, `test_font_source_single_truth`, `test_color_polish_ui_smoke`) all pass; `scripts\harness_check.ps1` passed.
Residual risk: `DefectListWidget(workflow="combined")` is confirmed unused in production (only `"tracking"`/`"trace"` are constructed by `ncr/embed.py`/`main_window.py`) but its empty-state toggle uses an aggregate open+closed count rather than the active tab's own count — a pre-existing imprecision, not newly introduced, and not exercised by any test or live code path.
Next action: None planned; flag if `workflow="combined"` is ever wired into production navigation, since its empty-state accuracy would then need the same per-tab fix already applied to `_on_tab_changed`.
Debug/RCA (when applicable):
Observed: Native screenshots showed warehouse pages with OS-native button icons, no visible card/panel boundaries, a flat-gray stats container, right-aligned form labels, and a plain-text zero-result line, while the equivalent supplier-event pages had none of these.
Root cause: `src/ncr/ui/ui_style.py`'s shared style helpers set `QWidget.setProperty("uiRole", ...)` — a property name never matched by any selector in `src/ui/_qss_*.py` (only `role="..."` selectors exist there); the NCR module also independently kept OS-native `QStyle.StandardPixmap` icon attachment on buttons/section titles, a pattern the supplier-event side had already dropped.
Fix: Rename the property key to `role` (and remap NCR-only role values to existing shared roles) across every NCR style helper; delete the icon-attachment call sites and the now-dead icon helper functions; add the two small missing QSS rules (`role="separator"`, `tone="success"`) rather than inventing new NCR-specific ones.
Harness update needed: no
Destination: `src/ncr/ui/ui_style.py`, `src/ncr/ui/defect_form.py`, `src/ncr/ui/defect_list.py`, `src/ui/_qss_base.py`, `src/ui/_qss_tabs.py`, `src/ui/main_window.py`, `tests/test_ncr_defect_form_product_selection.py`, `docs/harness/closed-loop-log.md`
