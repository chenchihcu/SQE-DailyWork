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
- Cursor rules: `.cursor/rules/agents_gateway.mdc`.
- Active risks: `docs/risk-ledger.md`.
- Closed-loop harness: `docs/harness/README.md`, `docs/harness/closed-loop-log.md`, `docs/harness/quality-score.md`, and `docs/harness/doc-gardening.md`.
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
- **Lightweight visit defect notes**: `登錄訪廠紀錄` and `登錄訪廠缺失` share the visit-record form. A visit may contain multiple `visit_product_sections` plus lightweight `visit_defect_notes` (`缺失內容` required, `改善內容` optional, `備註` optional). These notes are supplier visit/audit records for tracking only. They may become formal supplier anomaly events only through an explicit confirmation/conversion path that keeps the `visit_id` link.
- **Anomaly ↔ Visit link (`anomalies.visit_id`)**: The schema allows `NULL` for legacy, tests, or when the user turns off visit sync. Product-default behavior (e.g. `defect_form_widget`「同步建立訪廠紀錄」checked): call `create_anomaly_with_visit_link` with `sync_visit=True` so the system reuses a same-day visit or creates one and stores `visit_id`. Use `sync_visit=False` or `create_anomaly` without `visit_id` only when intentionally omitting a visit link.
- **Closure (`anomalies.status`)**: Only `待處理` / `已結案`. Closing goes through `close_anomaly`: non-empty `improvement_desc` (改善說明) is required, and `closed_at` is set (normalized date; service/repository defaults apply). Do not refer to legacy names `verification_result` / `verified_at` in new code—they are not v2 columns.
- **Statistics boundary**: Supplier event statistics must query supplier event tables; warehouse nonconforming-product statistics must query `defect_records`. Do not combine these counts into a generic quality-abnormality metric unless the UI explicitly labels and separates both sources.
- **Import boundary**: Keep database import paths because future ERP imports will reduce manual entry. Imports that update shared master data must target `suppliers/products` with preview, backup, and reconciliation. Warehouse compatibility imports may update warehouse support tables only when clearly labeled as warehouse-module data.
- **Soft Delete**: Use `is_active: bool = True` for Models. Filter by `is_active=True` in all standard queries.
- **Temporal Standard**: Use ISO-8601 dates in services; UI shows localized Traditional Chinese where applicable.
- **Badge and List Count Alignment**: When updating sidebar navigation badges or dashboard cards for specific scoped items (e.g. '單獨異常' / '訪廠發現異常'), ensure that the count query aligns exactly with the filters applied to the lists displayed on the right. For example, the badge count for '單獨異常' must only count open anomalies without a visit link (`visit_id IS NULL OR visit_id = ''`), rather than using a general un-scoped count of all open anomalies.
- **Supplier Event List Columns (Anomaly No over Date)**: For all supplier event lists (such as the EventListWidget query tabs and the HomeWidget backlog table), the first column must be named "異常單號" (Anomaly Number) instead of "日期" (Date). The row rendering must show the `ref_no` (anomaly number) if present, and fallback to `event_date` (date) only for visit records that lack an anomaly number. When sorting by this column, if the `ref_no` is empty (e.g., visits), the system must fallback to sorting by `event_date` to ensure stable sorting.

## 3. UI/UX & Styling Standards (Slate + Electric Blue)
- **Terminology**: Keep labels and status terms consistent with existing dialogs and `src/ui/popup_i18n.py` patterns.
- **Grid Layout** (single source of truth: `src/ui/layout_constants.py`; values pinned by `tests/test_layout_constants.py` — import the constants, do not hardcode pixels):
  - Standard form area max width: `960px` (`FORM_MAX_WIDTH`, dialog `setMaximumWidth`).
  - Top-level page outer frame `PAGE_OUTER_MARGINS = (24, 24, 24, 24)`; main panel inner padding `PANEL_MARGINS = (12, 10, 12, 10)`.
  - 2-column grid rhythm: `GRID_GUTTER = 12`, `ROW_GAP = 8` for `QGridLayout`; `QFormLayout` uses `FORM_HORIZONTAL_SPACING = 16` / `FORM_VERTICAL_SPACING = 12`.
- **Aesthetics**: High density, light Slate surfaces, Electric Blue primary actions, card-based professional internal-tool look.
- **Workbench topology**: Keep the first screen operational, not decorative. Do not reintroduce hero/cover panels, feature tours, project-structure copy, or card-in-card wrappers for the home workbench.
- **Dashboard & Stats Refresh Standard**: For any dashboard or analytical statistics pages (where underlying database records can be modified by other management tabs), always provide a manual "重新整理" button (styled as `variant="secondary"` and positioned to the left of the primary "匯出 Excel" button). Additionally, when switching to these statistics pages in `MainWindow._switch_primary_page`, always force a call to `refresh_data()` to ensure visual charts are up-to-date, bypassing any one-off lazy loading flags.
- **UI removal semantics**: When the user says a UI element should be removed or not displayed, remove it from the visible layout and object tree unless a compatibility boundary truly requires keeping it. Hidden compatibility widgets require an explicit code comment, focused test, and native visual evidence proving no visible residue.
- **Qt compatibility widgets**: Test/proxy widgets such as dummy `QTabWidget`, hidden `QScrollArea`, or placeholder `QWidget` instances must be hidden immediately or kept parentless until intentionally used. Do not drive native visual probes through hidden compatibility proxies; probes must operate on real visible controls, routes, or scroll positions.
- **Feedback**: `QMessageBox` for confirmations; destructive actions use explicit confirm dialogs.

## 4. Coding & Refactoring Standards
- **Desktop QSS**: Prefer QSS roles (`role`, `variant`) and theme tokens over ad-hoc per-widget `setStyleSheet`, except where already established (e.g. tech-transfer cards).
- **Rename before Delete**: When removing fields, rename them first (e.g., `status` -> `status_DELETING`) to let the compiler highlight all references.
- **Grep Search**: After changes, verify application directories (`src/database/`, `src/services/`, `src/ui/`) are clean of old terms.

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
- Keep one-off bug details out of global Codex rules. Promote only reusable project knowledge into `docs/harness/closed-loop-log.md` or the relevant source-of-truth doc.
- For complex changes, create a short plan under `docs/exec-plans/active/` and move it to `docs/exec-plans/completed/` after completion.
- This format does not weaken global Hard Triggers, `blocked`, `not verified`, or `not pass` semantics.

## 7. Verification
- Small text/docs-only edits: focused inspection plus `scripts\harness_check.ps1` when harness files changed.
- Python code edits: use `scripts\verify.ps1` when practical; otherwise run the closest focused unittest or compile check and report the gap.
- UI behavior changes: use offscreen Qt only for structural smoke checks such as startup, widget existence, and signal wiring.
- UI visual review, screenshots, typography, and Chinese text rendering checks must use the native Windows Qt platform through `scripts\qt_visual_probe.py` or an equivalent native-platform capture. Do not treat `QT_QPA_PLATFORM=offscreen` screenshots as visual evidence because offscreen can miss Windows CJK fonts and render square glyphs.
- Data migration, destructive data changes, or export/data-contract changes follow the global Hard Trigger rules and require explicit verification evidence.

## 8. Multi-Assistant Coexistence
- **Coexistence Policy:** Codex, Claude Code, Cursor, and Gemini/Antigravity operate in the same workspace. All assistants must treat this file as the authoritative repository policy. Cursor rules are defined in `.cursor/rules/` and point to this file. **Trunk-Based Development (TBD)** 為所有 AI 工具的強制開發流程：一律直接提交到 `main`，禁止開 feature branch。
- **Gemini (Antigravity) Flow & Workflow Sync:** When operating via Antigravity, strictly follow `~/.gemini/GEMINI.md` triage (L0/L1/M1/F1/F2), implementation plans, and the Gate A~F checklists. Deliverables (plans, tasks, walkthroughs) must use Traditional Chinese (繁體中文). If changes were directly made using Cursor or Claude Code without prior Gemini plan approval, the developer must perform `git diff` when switching back to Gemini, manually update `walkthrough.md` to document changes, and resolve any process gaps before completing the task.
- **Command Policy & Codex Sync Rule:** Any modifications or additions to verification and development commands must be synchronized with the Python-like rules in `.codex/rules/project.rules` to prevent Codex sandbox blocks.
- **AI Rules Compatibility:** Read `docs/harness/ai-rules-compatibility.md` before cross-tool handoff or governance edits. Official claims, local observations, audit inferences, assumptions, and `not verified` items must remain labeled.
- **Source-Control Boundary:** If `git status --short` is noisy, the source baseline is absent, or the repo was just initialized, use one writer per worktree. Do not run parallel writing AI tools in the same checkout. Prefer Antigravity New Worktree Mode for complex or parallel tasks; Local Mode is for small interactive work only.
