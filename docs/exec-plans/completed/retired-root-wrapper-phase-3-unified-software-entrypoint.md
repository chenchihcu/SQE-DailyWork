# Retired Historical Reference

This file preserves the former outer `SQE DailyWork` wrapper/launcher plan for
audit history. It is no longer the active architecture after the root-flatten
normalization: `C:\Users\user\Documents\SQE DailyWork` is now intended to be the
single project root, and the normal entrypoint is the root `main.py`.

# Phase 3 Plan - Unified Software Entrypoint

Date: 2026-06-02

## Objective

將 `SQE DailyWork` 的每日入口從終端機選單升級為桌面軟體入口視窗，並讓使用者感覺這是一套完整工具，而不是兩套被臨時接在一起的軟體。

Phase 3 的核心是 UI/UX 與啟動體驗整合，不是 source merge，也不是 database merge。

## Current-State Evidence

Root workspace:

- `run_dailywork.ps1` currently renders a terminal menu with `Write-Host` and `Read-Host`.
- `run_dailywork.bat` currently opens PowerShell and runs the terminal menu.
- Root `README.md` still describes the root entry as a menu.
- Root `AGENTS.md` forbids flattening child source folders and forbids DB merge without explicit High-Risk planning.
- `scripts/backup_data.ps1` and `scripts/verify_all.ps1` already exist and should remain available for operations and verification.

SQETOOL:

- Phase 2 added the home quick action `開啟不良品追蹤`.
- `SQETOOL/services/defect_manager_launcher.py` launches `defect_manager/DefectManager.bat` as a separate subprocess.
- `SQETOOL/docs/ui-layout-theme-contract.md` already documents the Defect Manager external launcher entrypoint.
- `SQETOOL` remains the primary daily SQE workflow shell.

Defect Manager:

- `defect_manager/DefectManager.bat` starts `main.py` from its own folder.
- `defect_manager/docs/ui-ux-design-reference.md` already states that the tool should look like the same company's product family.
- Defect Manager remains the preserved NCR / nonconforming-product tracking workflow.

Technical constraints:

- Do not import Defect Manager modules into SQETOOL in Phase 3.
- Do not merge `defect_manager/data/defect.db` and `SQETOOL/data/sqe_v2.db`.
- Do not remove terminal verification scripts; move daily user interaction away from terminal, but keep diagnostic commands available.
- Do not make root backup/verify buttons silently hide failures; surface output inside the GUI if these operations are exposed.

## RCA

Observed:

- Phase 1 gave one root entrypoint, but the root experience is still a terminal menu.
- Phase 2 made Defect Manager reachable from SQETOOL, but it still opens as a visibly separate product.
- User goal is now explicitly UI/UX-driven: the system should look like one software suite, not two detached apps.

Root cause:

- Early integration optimized safety and process boundaries first.
- The safe subprocess boundary was not paired with a GUI launcher, unified naming, unified window titles, or shared user-facing module semantics.
- Current launch wrappers show terminal text before opening GUI apps, which makes the workflow feel like scripts instead of software.

Fix direction:

- Add a root Qt launcher window as the default daily entry.
- Use windowless process launch for user-facing app starts.
- Keep CLI scripts as diagnostic and automation tools.
- Reframe child apps as modules under `SQE DailyWork` through naming, window titles, iconography, and shared UI tokens.

## Target UX Definition

The accepted Phase 3 UX is:

- The user double-clicks a software entrypoint and sees a Qt window, not a terminal menu.
- The first visible screen says `SQE DailyWork`.
- SQETOOL appears as the primary module, for example `SQE 工作台`.
- Defect Manager appears as an NCR module, for example `NCR / 不良品追蹤`.
- Technical names such as `SQETOOL` and `Defect Manager` may remain in tooltips, docs, logs, and diagnostics, but should not dominate the normal UI.
- Backup and verification can be launched from the GUI only if their output is shown in an in-window log panel.
- Existing command-line operations remain available for engineering use.

## UI/UX Entrypoint Matrix

| Entrypoint | Open path | Target file / class | Parent | Sizing policy | Console exposure | Theme source | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Preferred daily entry | `run_dailywork.vbs` or shortcut | `launcher/dailywork_launcher.py` / `DailyWorkLauncherWindow` | Windows desktop | 1020 x 640 preferred, 95% screen cap | none | root launcher tokens mirrored from SQETOOL | native manual smoke + offscreen structure test |
| Diagnostic fallback | `run_dailywork.ps1 -Action console-menu` | existing terminal menu function | PowerShell | terminal controlled | terminal expected | n/a | manual command smoke |
| Primary SQE module | GUI button `進入 SQE 工作台` | `SQETOOL/main.py` | root launcher process service | child app's own sizing | none for normal launch | SQETOOL theme | manual native smoke + `SQETOOL/scripts/verify.ps1` |
| NCR module | GUI button `開啟 NCR / 不良品追蹤` | `defect_manager/main.py` | root launcher process service | child app's own sizing | none for normal launch | Defect Manager theme harmonized to DailyWork | manual native smoke + `defect_manager/scripts/verify.ps1` |
| Backup | GUI button `備份資料庫` | `scripts/backup_data.ps1` through hidden process with captured output | root launcher | in-window log panel | none unless launched manually | root launcher log style | focused process-service test + manual smoke |
| Verify all | GUI button `執行健康檢查` | `scripts/verify_all.ps1` through hidden process with captured output | root launcher | in-window log panel | none unless launched manually | root launcher log style | root verify gate |

## Before / After Container Topology

Before:

- Root entry:
  - PowerShell terminal menu.
  - No software window.
- SQETOOL:
  - `MainWindow`
  - `SidebarNav`
  - `ContentHost`
  - `PageHeaderBar`
  - `QStackedWidget#PageStack`
  - Home quick action launches Defect Manager externally.
- Defect Manager:
  - `MainWindow`
  - Sidebar frame.
  - `QStackedWidget#workflowStack`
  - functional dialogs and nested tabs.

After target topology:

- Root entry:
  - `DailyWorkLauncherWindow`
  - single shell container with product header, module action list, status area, and optional diagnostics/log panel.
  - no nested decorative cards.
- SQETOOL:
  - remains the primary full workflow shell.
  - user-facing naming aligns with `SQE DailyWork`.
- Defect Manager:
  - remains a separate process.
  - user-facing title and labels align with the NCR module identity.

Flattening decisions:

- No existing root GUI container can be flattened because root currently has no GUI container.
- The new launcher must start with a flat layout: one shell, one action region, one status/log region.
- Do not add card-in-card root decoration.
- Child app container flattening is out of scope unless a visual probe shows a specific mismatch or clipping problem.

Preserved functional containers:

- SQETOOL `SidebarNav`, `ContentHost`, `PageStack`, and dialog footer wrappers.
- Defect Manager sidebar, workflow stack, tab hosts, scroll areas, and dialog action footers.
- Root scripts for backup and verification as diagnostic entrypoints.

## Role-Based Feasibility Discussion

| Role | Feasibility view | Concern | Required guardrail | Decision |
| --- | --- | --- | --- | --- |
| SQE workflow owner | Feasible and desirable because the user starts from one branded daily hub. | NCR users must not lose the known tracking flow. | Keep NCR workflow reachable and label it as a DailyWork module. | Go. |
| UI/UX owner | Feasible if terminology and visual hierarchy stop presenting two product names. | Root launcher alone is not enough if child windows still look unrelated. | Unified window titles, shared colors/font rhythm, module labels, and no terminal-first flow. | Go with visual cohesion work. |
| Desktop architect | Feasible with separate processes and `pythonw.exe` / hidden process launch. | In-process merge remains unsafe because import roots still collide. | Keep subprocess boundary; do not import child modules across apps. | Go for process-level shell only. |
| Data owner | Feasible because Phase 3 does not mutate SQLite data. | Backup/verify GUI buttons could be mistaken for data workflows. | Backup copies only; verification is read/check only; no DB merge. | Go. |
| QA / harness owner | Feasible if launcher commands and UI structure are testable. | Manual native smoke is required to prove no console window remains. | Mock process launch in tests, then manually verify double-click behavior. | Go with manual gate. |
| Operations / support owner | Feasible if diagnostic commands remain available. | Removing terminal entirely can make failures opaque. | Keep CLI actions and show GUI log output for backup/verify failures. | Go. |
| Source-control / governance owner | Feasible as scoped root additions and small visible-copy edits. | Root `git` status is not verified because `git.exe` is unavailable in current PATH. | Avoid source moves; keep rollback file-scoped. | Go with status caveat. |

Consensus:

- Phase 3 should proceed as a software launcher and visual cohesion phase.
- It should not attempt source flattening, in-process embedding, or database migration.
- The strongest feasibility path is to make the daily entry look unified while preserving process and data boundaries.

## Implementation Plan

### Step 0 - Preflight

Tasks:

1. Run root backup:
   ```powershell
   .\scripts\backup_data.ps1
   ```
2. Confirm Python GUI runtime:
   - `SQETOOL\.venv\Scripts\pythonw.exe`
   - `SQETOOL\.venv\Scripts\python.exe`
   - PySide6 import availability.
3. Confirm existing app launch files:
   - `SQETOOL\main.py`
   - `defect_manager\main.py`
   - `SQETOOL\run_app.bat`
   - `defect_manager\DefectManager.bat`
4. Run current root gate:
   ```powershell
   .\scripts\verify_all.ps1
   ```

Stop-loss:

- Stop if current verification fails before Phase 3 edits.
- Stop if `pythonw.exe` is unavailable and no no-console launcher alternative is available.

### Step 1 - Add Root GUI Launcher Service

Candidate files:

- `launcher/process_service.py`
- `launcher/path_resolver.py`
- `launcher/__init__.py`

Responsibilities:

- Resolve workspace root.
- Resolve child app Python executable, preferring `SQETOOL\.venv\Scripts\pythonw.exe` for GUI starts.
- Start SQETOOL with:
  - `cwd=SQETOOL`
  - `PYTHONPATH=SQETOOL`
  - no terminal window.
- Start Defect Manager with:
  - `cwd=defect_manager`
  - `PYTHONPATH=defect_manager`
  - no terminal window.
- Start backup/verify scripts through a hidden process with captured stdout/stderr for GUI log display.
- Return structured results for missing paths, launch failures, and process start success.

Testing:

- Mock process start and assert command, working directory, environment, and no-console launch settings.
- Test missing Python, missing app folder, missing script, and process failure.

### Step 2 - Add Root Qt Launcher Window

Candidate file:

- `launcher/dailywork_launcher.py`

Window contract:

- Title: `SQE DailyWork`
- Object name: `DailyWorkLauncherWindow`
- Preferred size: around `1020 x 640`, capped to active screen.
- CJK font priority mirrors SQETOOL / Defect Manager.
- Primary action: `進入 SQE 工作台`.
- Secondary module action: `開啟 NCR / 不良品追蹤`.
- Utility actions: `備份資料庫`, `執行健康檢查`, `開啟說明`.
- Status area shows last action, target path, and failure messages.
- Optional collapsible log panel for backup/verify output.

UI rules:

- Use one operational shell, not a marketing landing page.
- Do not use nested cards or decorative gradients.
- Use shared Slate + Electric Blue style direction.
- Avoid presenting `SQETOOL` and `Defect Manager` as two unrelated brands in the main visual hierarchy.
- Keep buttons large enough for Traditional Chinese labels without clipping.

Testing:

- Offscreen Qt structure test:
  - window creates.
  - required buttons exist by object name.
  - labels and tooltips match the contract.
  - clicking buttons calls the service layer, mocked.
- Native manual visual smoke:
  - no clipped CJK text.
  - no terminal remains visible.
  - root launcher fits current screen.

### Step 3 - Replace Default Terminal Entry

Candidate files:

- `run_dailywork.vbs`
- `run_dailywork.bat`
- `run_dailywork.ps1`

Target behavior:

- Preferred double-click entry uses `run_dailywork.vbs` or a generated shortcut to start `pythonw.exe` without a terminal window.
- `run_dailywork.bat` may remain as a compatibility wrapper but should start the GUI and exit quickly.
- `run_dailywork.ps1` should default to GUI behavior for interactive entry.
- Preserve non-interactive actions:
  - `-Action sqetool`
  - `-Action defect`
  - `-Action backup`
  - `-Action verify`
  - `-Action readme`
- Move the old terminal menu to a diagnostic-only action such as `-Action console-menu` if retained.

Acceptance:

- Double-clicking the preferred entry shows a GUI window, not a terminal menu.
- Engineering commands still work from PowerShell.
- Failures show either an in-GUI message or a deliberate diagnostic fallback, not silent failure.

### Step 4 - Harmonize User-Facing Module Identity

Candidate files:

- `SQETOOL/ui/main_window.py`
- `SQETOOL/ui/widgets/home_widget.py`
- `SQETOOL/docs/ui-layout-theme-contract.md`
- `defect_manager/ui/main_window.py`
- `defect_manager/docs/ui-ux-design-reference.md`
- root `README.md`

Target changes:

- Normal UI labels:
  - Product suite: `SQE DailyWork`
  - Main module: `SQE 工作台`
  - NCR module: `NCR / 不良品追蹤`
- Window titles:
  - `SQE DailyWork - SQE 工作台`
  - `SQE DailyWork - NCR 不良品追蹤`
- Tooltips may preserve technical names:
  - `SQETOOL`
  - `Defect Manager`
- Avoid saying the user is "opening another app" in primary UI copy; say they are opening the NCR module.

Boundaries:

- No data-field rename.
- No database table rename.
- No export column change.
- No import namespace refactor.

### Step 5 - Optional Shared Visual Token Pass

Scope:

- Small UI token harmonization only if visual probe shows the root launcher and child windows do not look like one suite.

Candidate approach:

- Root launcher mirrors SQETOOL colors, font, button roles, and spacing.
- Defect Manager title/sidebar/header can be adjusted toward DailyWork naming and rhythm without rewriting workflows.
- Do not create a large shared cross-project design system in Phase 3.

Stop-loss:

- Stop if token changes require touching many page-local styles across both apps.
- Defer broader visual refactor to a separate Phase 4 UI harmonization plan.

### Step 6 - Documentation

Candidate files:

- root `README.md`
- `MERGE_FEASIBILITY_PLAN.md`
- `SQETOOL/docs/ui-layout-theme-contract.md`
- `defect_manager/docs/ui-ux-design-reference.md`

Documentation requirements:

- State that the preferred daily entry is a software window.
- Keep terminal commands documented as diagnostics/automation.
- Document that Phase 3 still uses separate processes and separate databases.
- Document manual native smoke as required evidence for the no-terminal claim.

### Step 7 - Verification

Focused tests:

```powershell
.\SQETOOL\.venv\Scripts\python.exe -m unittest discover -s launcher\tests
```

Launcher compile/import:

```powershell
.\SQETOOL\.venv\Scripts\python.exe -m compileall launcher
```

Child project gates:

```powershell
.\scripts\verify_all.ps1
```

Native manual smoke:

1. Double-click the preferred root entry.
2. Confirm a `SQE DailyWork` GUI window appears.
3. Confirm no terminal menu remains visible as the daily entry.
4. Click `進入 SQE 工作台`.
5. Confirm SQETOOL opens with a DailyWork-aligned title and remains usable.
6. Click `開啟 NCR / 不良品追蹤`.
7. Confirm the NCR tracking window opens with DailyWork-aligned title/copy.
8. Run `備份資料庫` from the GUI if implemented.
9. Confirm backup output appears in the GUI log area, not a separate terminal.
10. Close child windows and confirm the launcher remains stable.

Verification status rule:

- The no-terminal UX claim is `verified` only after the native manual smoke is performed.
- Offscreen Qt structure tests are not enough to prove no terminal appears.

## Acceptance Criteria

Phase 3 is accepted when:

- The preferred daily entry opens a GUI launcher window.
- The normal daily entry no longer presents a terminal menu.
- SQETOOL and Defect Manager are presented as modules under `SQE DailyWork`.
- SQETOOL remains the primary module.
- Defect Manager remains reachable as `NCR / 不良品追蹤`.
- Backup and verification remain available.
- No database schema, migration, export, or data merge changes occur.
- No child source folder flattening occurs.
- Root launcher tests pass.
- `scripts/verify_all.ps1` passes.
- Native manual smoke confirms no terminal-first UX.

## Rollback

If Phase 3 fails before acceptance:

- Delete or disable:
  - `launcher/`
  - `run_dailywork.vbs`
  - root launcher tests
- Revert:
  - `run_dailywork.bat`
  - `run_dailywork.ps1`
  - root `README.md`
  - `MERGE_FEASIBILITY_PLAN.md`
  - SQETOOL / Defect Manager visible title or label edits
- Keep:
  - `scripts/backup_data.ps1`
  - `scripts/verify_all.ps1`
  - Phase 2 SQETOOL home quick action
- No DB restore is expected because Phase 3 should not write application data.

## Risks

| Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- |
| `pythonw.exe` missing | GUI launcher cannot start without terminal | Preflight check and explicit fallback message | controlled |
| `.bat` briefly flashes a console | User may still perceive terminal startup | Preferred `.vbs` entry; `.bat` as compatibility fallback | controlled |
| Hidden process failures become invisible | User cannot diagnose launch failure | In-GUI status/log panel and diagnostic CLI actions | controlled |
| Child windows still feel like separate brands | UI/UX goal not fully met | Harmonized root launcher labels, SQETOOL title, NCR title, and NCR sidebar brand | controlled |
| Over-scoping into source/data merge | High regression risk | Keep Phase 3 process-level only | controlled |
| Visual token changes create page regressions | CJK clipping or layout drift | Native visual probe and scoped token edits | open |

## Go / No-Go

Go:

- Build a root GUI launcher.
- Make GUI the preferred daily entry.
- Launch child modules without terminal windows.
- Harmonize user-facing module identity.
- Keep CLI diagnostics.

No-go:

- In-process embedding.
- Source folder flattening.
- Database merge.
- Export contract changes.
- Removing backup/verify scripts.

Conditional:

- Defect Manager visual token changes are allowed only if scoped and verified.
- Wider child-app UI harmonization should become a separate Phase 4 plan if it touches many pages.

## Done Checklist

- [x] Backup created before implementation.
- [x] `pythonw.exe` / no-console launch path confirmed.
- [x] Root GUI launcher service implemented.
- [x] Root Qt launcher window implemented.
- [x] Default daily entry no longer shows terminal menu.
- [x] Existing CLI diagnostics preserved.
- [x] SQETOOL / NCR module naming harmonized.
- [x] Root launcher tests added and passing.
- [x] `scripts/verify_all.ps1` passes.
- [x] Native manual smoke verifies GUI-first, no-terminal entry.

## Completion Notes

- Implemented on 2026-06-02.
- Backup before implementation: `data_backups/20260602-195340`.
- Additional GUI backup smoke created `data_backups/20260602-200747`.
- Preferred no-terminal entry: `run_dailywork.vbs`.
- Compatibility entry: `run_dailywork.bat`.
- Diagnostic entry: `run_dailywork.ps1 -Action console-menu`.
- Native process smoke detected `SQE DailyWork` launcher window through `wscript.exe run_dailywork.vbs` and reported `visible_terminal_windows=0`.
- Native module smoke launched `SQE DailyWork - SQE 工作台` and `SQE DailyWork - NCR 不良品追蹤` through the root service and reported `visible_terminal_windows=0`.
- Root `scripts/verify_all.ps1` now includes root launcher compile/tests before both child project gates.
