# Phase 2 Plan - SQETOOL Primary Shell Link for Defect Manager

Date: 2026-06-02

## Objective

Make SQETOOL the primary desktop entrypoint that can open `defect_manager` as the preserved NCR / nonconforming-product tracking workflow.

This phase is an operational UI integration, not a source-code merge and not a database merge.

## Current-State Evidence

Workspace evidence:

- Root phase 1 files exist: `run_dailywork.ps1`, `run_dailywork.bat`, `scripts/backup_data.ps1`, `scripts/verify_all.ps1`, root `README.md`, root `AGENTS.md`.
- `defect_manager/DefectManager.bat` now resolves paths relative to its own folder.
- `scripts/verify_all.ps1` passed for both child projects during Phase 1.

SQETOOL evidence:

- `SQETOOL/AGENTS.md` requires preserving the single-user PySide6 + SQLite desktop model, v2 data contracts, existing storage paths, and terminology alignment.
- `SQETOOL/ui/main_window.py` owns the shell and route methods.
- `SQETOOL/ui/sidebar_nav.py` owns the fixed left navigation and footer quick-create button.
- `SQETOOL/ui/widgets/home_widget.py` owns the home quick-action panel.
- `SQETOOL/docs/ui-layout-theme-contract.md` defines the entrypoint matrix, screen-fit rules, and theme/layout rules.
- `SQETOOL/tests/test_home_recent_events_panel.py` already checks home quick-action button contract and layout count.
- `SQETOOL/tests/test_top_nav_compact_height.py` already checks sidebar shape and expected nav item count.

Technical constraint:

- Do not import `defect_manager.ui`, `defect_manager.services`, or other Defect Manager modules into the SQETOOL Python process in Phase 2. The two apps still use top-level import roots such as `ui` and `services`, so in-process import is unsafe before namespacing.

## RCA

Observed:

- Phase 1 gives one root daily-work menu, but daily users still need to leave SQETOOL to open Defect Manager.
- SQETOOL is the broader SQE workflow shell and should become the visible primary app.
- Defect Manager still has useful NCR / nonconforming-product tracking workflows that should remain reachable.

Root cause:

- The two apps were built as independent desktop projects with separate import roots, separate UI shells, and separate SQLite databases.
- A direct in-process merge would risk import collisions and unintended data-contract changes.

Fix direction:

- Add a clearly labeled SQETOOL UI action that launches Defect Manager as a separate process.
- Keep source namespaces and databases separate.
- Use SQETOOL's existing quick-action style and root/child launcher boundaries.

## Scope

In scope:

- Add one visible SQETOOL action to open Defect Manager.
- Add a small SQETOOL launcher service/helper that starts `defect_manager/DefectManager.bat`.
- Add graceful user feedback for launch failure.
- Add focused tests for launcher resolution, UI button contract, and no sidebar-count regression.
- Update SQETOOL README and UI layout/theme contract.

Out of scope:

- Moving either child project.
- Importing Defect Manager widgets into SQETOOL.
- Sharing one QApplication process.
- Merging `defect.db` and `sqe_v2.db`.
- Changing SQETOOL anomaly/visit data contracts.
- Changing Defect Manager workflows or database schema.

## UI/UX Entrypoint Decision

Recommended first entrypoint:

- Add a fourth button in `HomeWidget` quick actions.
- Button label: `開啟不良品追蹤`
- Tooltip/status tip: `開啟 Defect Manager（NCR / 不良品追蹤）`
- Tone: new neutral/utility tone or existing secondary style, not primary anomaly tone.

Why home quick action first:

- It is visible on the first page without changing the main navigation model.
- It matches the current user mental model: quick action, separate workflow, occasional jump.
- It avoids changing `SidebarNav` button count, which is a higher-regression area with dedicated tests.
- It keeps Defect Manager framed as an adjacent preserved workflow, not as a new SQETOOL data module.

Deferred alternative:

- Add a second sidebar footer action below `＋ 新增異常` only after the home quick action proves useful.
- Do not add a seventh sidebar navigation page in Phase 2 because it would imply an in-process SQETOOL page that does not exist.

## UI/UX Container Scan

Before topology:

- `SQETOOL/MainWindow`
  - `SidebarNav`: functional navigation container.
  - `ContentHost`: semantic shell boundary.
  - `PageHeaderBar`: functional page context.
  - `QStackedWidget#PageStack`: functional page host.
  - `HomeWidget`
    - `HeroBannerFrame`: semantic overview.
    - KPI panel: semantic metrics region.
    - `HomeQuickActionPanel`: semantic quick-action container with title + 3 buttons.

After target topology:

- Keep the same topology.
- Add one new button inside `HomeQuickActionPanel`.
- Do not add new wrapper cards, nested panels, tab pages, or stacked pages.

Flattening decisions:

- No container flattening is planned for Phase 2.
- Existing containers are functional or semantic for this change.
- The next concrete flattening candidate, if future UI work is requested, is a separate audit of `HomeWidget` info/quick panels and repeated panel/card role nesting, not part of this launcher phase.

Preserved functional containers:

- `SidebarNav`
- `PageHeaderBar`
- `ContentHost`
- `PageStack`
- `HomeQuickActionPanel`

## Implementation Plan

### Step 0 - Preflight

Tasks:

1. Run `.\scripts\backup_data.ps1` from root.
2. Run `.\scripts\verify_all.ps1` from root or at minimum `.\SQETOOL\scripts\verify.ps1`.
3. Confirm `defect_manager\DefectManager.bat` exists.
4. Confirm `SQETOOL` starts with current verify gate before UI changes.

Output:

- Backup folder path.
- Verification result.

Stop-loss:

- Stop if SQETOOL verification is failing before Phase 2 edits.
- Stop if Defect Manager launcher file is missing.

### Step 1 - Add Launcher Helper

Candidate file:

- `SQETOOL/services/defect_manager_launcher.py`

Responsibilities:

- Resolve workspace root from `SQETOOL/services/`.
- Resolve `defect_manager/DefectManager.bat`.
- Return structured result: success/failure/message/path.
- Launch Defect Manager using a separate process.
- Avoid importing Defect Manager Python modules.
- Avoid database writes.

Preferred process boundary:

- Use `subprocess.Popen` to start a Windows command that runs `DefectManager.bat` from `defect_manager` as working directory.
- Keep the process independent so closing Defect Manager does not close SQETOOL.

Failure cases to handle:

- Defect Manager folder missing.
- `DefectManager.bat` missing.
- `cmd.exe` / process launch failure.

Test target:

- New focused test, for example `SQETOOL/tests/test_defect_manager_launcher.py`.
- Mock `subprocess.Popen`.
- Assert working directory, launcher path, and failure messages.

### Step 2 - Add MainWindow Action Method

Candidate file:

- `SQETOOL/ui/main_window.py`

Tasks:

1. Add `open_defect_manager(self)` method.
2. Call `services.defect_manager_launcher.launch_defect_manager()`.
3. On success, show a short status or non-blocking feedback if there is an existing pattern; otherwise no modal success dialog is required.
4. On failure, show `QMessageBox.warning` with a concise actionable message.
5. Do not modify existing anomaly/visit creation methods.

Copy guidance:

- User-facing wording should be Traditional Chinese.
- Keep terminology consistent: `不良品追蹤`, `Defect Manager`, `NCR`.

Test target:

- Focused test can mock launcher result and confirm the method is callable.
- Avoid requiring a real external process in unit tests.

### Step 3 - Add Home Quick Action

Candidate file:

- `SQETOOL/ui/widgets/home_widget.py`

Tasks:

1. Add a quick-action button after `登錄訪廠缺失` and before `匯出週報簡報`.
2. Label: `開啟不良品追蹤`.
3. Tooltip/status tip: `開啟 Defect Manager（NCR / 不良品追蹤）`.
4. Connect click to `self.main_window.open_defect_manager`.
5. Reuse `_create_quick_action_button`.
6. Use secondary/utility visual priority, not the anomaly primary tone.

Test updates:

- Update `SQETOOL/tests/test_home_recent_events_panel.py`.
- Expected quick actions become:
  - `登錄訪廠紀錄`
  - `登錄訪廠缺失`
  - `開啟不良品追蹤`
  - `匯出週報簡報`
- `HomeQuickActionPanel` layout count changes from 4 to 5 because it includes title + 4 buttons.

### Step 4 - Theme/Tone Decision

Candidate files:

- `SQETOOL/ui/theme.py`
- possibly no theme change if existing secondary button style is enough.

Preferred:

- Avoid adding a new color if existing `quickActionButton` secondary styling is acceptable.
- If a new tone is needed, add a restrained neutral/utility tone through existing token/QSS patterns.

Stop-loss:

- If adding a new tone expands QSS more than the UI value justifies, keep existing secondary style.

### Step 5 - Documentation

Candidate files:

- `SQETOOL/README.md`
- `SQETOOL/docs/ui-layout-theme-contract.md`
- root `README.md` only if implementation changes the root-level usage story.

Tasks:

1. Update SQETOOL `Home quick actions` list.
2. Document that `開啟不良品追蹤` opens Defect Manager in a separate window.
3. Add the action to the UI layout entrypoint matrix as an external app launcher.
4. Keep data-contract sections unchanged.

### Step 6 - Verification

Focused checks:

```powershell
cd SQETOOL
.\.venv\Scripts\python.exe -m unittest tests.test_defect_manager_launcher
.\.venv\Scripts\python.exe -m unittest tests.test_home_recent_events_panel
.\.venv\Scripts\python.exe -m unittest tests.test_top_nav_compact_height
```

Broader checks:

```powershell
.\SQETOOL\scripts\verify.ps1
```

Root check after SQETOOL passes:

```powershell
.\scripts\verify_all.ps1
```

Manual smoke:

1. Launch SQETOOL.
2. Confirm the home quick-action panel shows `開啟不良品追蹤`.
3. Click it.
4. Confirm Defect Manager opens in a separate window.
5. Close Defect Manager.
6. Confirm SQETOOL remains open and responsive.

Native visual check:

```powershell
cd SQETOOL
.\.venv\Scripts\python.exe scripts\qt_visual_probe.py
```

Verification status expectation:

- Automated checks should be `verified`.
- Manual external-window launch can be `verified` only if actually clicked on native Windows.
- If the implementation turn does not launch the GUI manually, report that external-window launch is `not verified` and name the exact manual smoke steps above.

## Acceptance Criteria

Phase 2 is accepted when:

- SQETOOL home page has a clearly labeled `開啟不良品追蹤` quick action.
- Clicking the action opens Defect Manager as a separate process/window.
- SQETOOL remains open and responsive after launching Defect Manager.
- No SQETOOL database schema, migration, or export contract changes.
- No Defect Manager database schema changes.
- Existing SQETOOL navigation count stays unchanged.
- Focused tests pass.
- `SQETOOL/scripts/verify.ps1` passes.
- Preferably `scripts/verify_all.ps1` passes after the change.

## Rollback

Rollback files if Phase 2 fails before acceptance:

- Remove `SQETOOL/services/defect_manager_launcher.py`.
- Remove tests added for the launcher.
- Remove `open_defect_manager` from `SQETOOL/ui/main_window.py`.
- Remove the `開啟不良品追蹤` quick action from `SQETOOL/ui/widgets/home_widget.py`.
- Restore `SQETOOL/tests/test_home_recent_events_panel.py` expected count/actions.
- Revert SQETOOL README and UI layout docs to pre-Phase-2 wording.

No database restore is expected because Phase 2 should not mutate databases.

## Risks

Regression risks:

- Home quick-action layout may become crowded at the minimum supported viewport.
- A failed external launcher could confuse users if the message is vague.
- Using a modal success dialog would interrupt the user unnecessarily.
- Adding a sidebar item would make the navigation imply an in-process page; avoid in Phase 2.

Mitigations:

- Use existing quick-action sizing and native visual probe.
- Keep feedback concise and failure-only where possible.
- Mock subprocess behavior in tests.
- Preserve sidebar navigation count.

## Done Checklist

- [x] Backup created before edits.
- [x] Launcher helper implemented and tested.
- [x] Home quick action implemented.
- [x] Failure feedback implemented.
- [x] SQETOOL README updated.
- [x] UI layout/theme contract updated.
- [x] Focused tests pass.
- [x] `SQETOOL/scripts/verify.ps1` passes.
- [x] Root `scripts/verify_all.ps1` passes or gap is reported.
- [ ] Manual native smoke confirms Defect Manager opens from SQETOOL, or is reported `not verified` with next steps.

## Completion Notes

- Implemented on 2026-06-02.
- Manual native external-window launch remains to be verified by clicking `開啟不良品追蹤` in SQETOOL.
