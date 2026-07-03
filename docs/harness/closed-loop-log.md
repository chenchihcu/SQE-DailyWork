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

