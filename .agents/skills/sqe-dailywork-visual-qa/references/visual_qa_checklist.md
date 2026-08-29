---
name: sqe-dailywork-visual-qa
version: 1.1.0
description: 用於 SQE DailyWork 的 PySide6 視覺檢查與按鍵功能稽核。需原生 Windows Qt 視覺證據。Use this skill 當要做 UI 截圖分析、中文字體審查、防回歸檢查或執行全介面按鍵崩潰測試時。觸發詞包含「PySide6」「UI」「截圖」「screenshot」「CJK」「中文渲染」「typography」「視覺審查」「visual QA」「按鈕遺失」「按鍵功能稽核」「崩潰測試」「動態點擊」「button audit」。
allowed-tools: Read, Grep, Glob, Bash
---

# SQE DailyWork Visual QA

Use this skill for UI visual-polish tasks (layout, theme, CJK typography, screenshots) and dynamic button crash testing on the PySide6 desktop app.

For a broad multi-surface sweep (main shell + forms + every stats page), delegate to the `sqe-dailywork-qt-visual-reviewer` subagent. Use this skill for inline, single-surface checks while editing.

**Visual QA is not just "take a screenshot."** A `widget.grab()` PNG only proves the main Qt widget tree, at one DPI, in its default state, with populated data. The checklist below exists because everything outside that — other DPIs, empty/error states, minimum width, popups/menus/tooltips, toolbar button preservation, accessibility names, the NCR module's own font, the PDF export font, and silently-failing QSS — does not show up in a single happy-path screenshot.

## Required Context

- Read `AGENTS.md`, `.cursor/rules/agents_gateway.mdc`, `docs/harness/README.md`, and the target `src/ui/` file.
- Before adding any styling, check `src/ui/theme.py` and `src/ui/layout_constants.py` and reuse shared widgets. Prefer QSS `role` / `variant` and theme tokens over per-widget `setStyleSheet` (AGENTS.md §3–4). Pull layout values from `src/ui/layout_constants.py` (`FORM_MAX_WIDTH`, `GRID_GUTTER`, `ROW_GAP`, `PANEL_MARGINS`) instead of hardcoding pixels — those constants are the single source of truth (pinned by `tests/test_layout_constants.py`).
- The shell is a `SidebarNav` + `QStackedWidget` architecture, NOT a tab bar. Preserve the sidebar information architecture (首頁 / 事件管理 scope rows: 單獨異常 / 訪廠發現異常 / 訪廠紀錄 / 已結案 / 異常事件統計 / 不合格品 / 不合格品統計分析 / 基礎資料 / 顯示設定); do not reintroduce an in-page scope tab bar for the consolidated 事件管理 page (see `src/ui/main_window.py` and `README.md`). Keep the home screen operational (no hero/cover panels, 8-column backlog table). Keep SQE DailyWork terminology aligned with `README.md` and `src/ui/popup_i18n.py`.
- **單一字體來源 (Single Font Source of Truth)**：CJK 字體 fallback 鏈僅定義於 `src/ui/theme.py`（`PREFERRED_CJK_FONT_FAMILIES` / `CJK_FONT_FAMILY_CSS`）；`src/ncr/ui/ui_style.py` 必須引入使用，禁止重新定義。字重策略 (僅限 CJK 400/700) 記錄於 `.claude/rules/visual_evidence_rules.md` §2。

## Visual Evidence Rule

- `QT_QPA_PLATFORM=offscreen` is structural smoke only — never visual evidence (it can miss Windows CJK fonts and render 方框).
- Visual screenshots, CJK rendering, font, and typography judgments must use native Windows Qt via `scripts\qt_visual_probe.py` (it auto-forces `QT_QPA_PLATFORM=windows` on Windows).
- **Automated Mode & Anti-Deadlock Guard**: Probes and test harnesses must run with `SQE_PROBE=1` or `SQE_TESTING=1` so that `MainWindow.closeEvent` and destructive action handlers bypass interactive modal question dialogs (`QMessageBox.question`). Custom event filters mounted on `QApplication` must directly `return False` for unhandled events to prevent PySide6 C++ trampoline recursion.
- **Read the PNG, not the console.** The probe prints CJK to the console as cp950 mojibake — that is a display artifact, NOT broken data. Judge CJK only from the saved PNG.
- **`grab()` cannot capture top-level popups.** `QMenu` (e.g. the event action menu), `QComboBox` dropdown lists, and tooltips render as separate native surfaces that a parent-widget `grab()` does not include. Verify those with a **structural assert** (e.g. `widget.toolTip()` / `accessibleName()` is set for elided cells, menu actions exist), not a screenshot.


## Running the probe

Interpreter: `.venv\Scripts\python.exe` (Python 3.14.3) — not the `.uv-python/3.12` tree.

```
.venv\Scripts\python.exe scripts\qt_visual_probe.py --target main --output Outputs\visual_qa\probe.png
```

- `--target` covers every surface family. Non-`main` targets write several suffixed PNGs:
  - `main` — shell (lands on the 事件管理 page) · `event-create` — anomaly / visit create pages · `form-density` — visit / supplier / product / warehouse / quick-product dialogs
  - `event-list` — consolidated 事件管理 table, long-CJK stress, all 4 scope tabs · `master-data` — 供應商 / 產品 master tables
  - `ncr-tracker` — warehouse 建立 / 待處理 / 歷史 tabs (list views, not just the create form)
  - `stats-stress` — 4 異常統計 charts with long-name stress · `ncr-stats` — NCR 2×2 grid
  - `appearance-settings` — appearance preferences dialog (default & comfortable large) · `workbench` — anomaly management workbench · `dialog-density` — dense workbench write dialogs
  - `empty-states` — empty event list / master / NCR-unavailable placeholder · `pdf-export` — sample event PDF + PDF font report
- `--scale 1.0,1.25,1.5` — capture at multiple DPIs (one child process per scale; required by §11). Filenames get an `@1.25x` suffix.
- `--min-width` (or `--size 1024x680`) — capture resizable surfaces at the contract minimum to catch CJK clipping.
- Default output is the OS temp dir; pass `--output Outputs\...` so artifacts land under `Outputs/` per repo convention.
- `--allow-offscreen` / `--no-screenshot` are for structural-only runs; label any such evidence as structural.

The probe is self-checking — read its JSON, do not eyeball platform validity:

- `visual_trustworthy: true` (native platform AND a CJK-capable main font) is required before any visual claim.
- Also check `cjk_font_ok`, **`ncr_cjk_font_ok`** (NCR module font), `qt_platform`, `selected_font`, `scale` / `device_pixel_ratio`, and **`qss_unknown_property_warnings`** (must be `0`).
- For `pdf-export`, also check `pdf_font_family` / `pdf_cjk_font_ok` (the PDF font chain is separate from the Qt app font).
- Exit codes: `0` ok · `2` refused offscreen for a visual run · `3` not visual-trustworthy. A non-zero exit means your screenshot is NOT valid visual evidence.

## Visual regression

`scripts\qt_visual_regress.py --target <t>` diffs the current capture against a committed baseline in `tests/visual_baseline/`. Baselines are generated natively with `--update` (see that folder's README). The check **skips** (never false-passes) when the environment does not match the baseline manifest. Refresh baselines deliberately after an intended visual change and review the diff.

## UI Button Functional Audit (動態按鍵功能稽核)

除了靜態視覺截圖，為防止因刪除欄位、槽函數或是元件綁定導致應用程式在點擊特定按鈕時崩潰，請使用 `scripts\button_audit_report.py`。
此腳本會在隔離的臨時測試資料庫環境中，自動實例化所有主要 UI 頁面（包含 MainWindow, EventCreatePage, MasterData 等），並模擬點擊每一個 `QAbstractButton` 元件（總計超過 70 個）。

執行方式：
```
.venv\Scripts\python.exe scripts\button_audit_report.py
```

- **適用時機**：大規模重構、移除屬性或重新佈局表單後，做為比視覺檢查更深一層的功能性防崩潰保證。
- **已知限制（2026-08-28，已緩解）**：Orchestrator 以 subprocess-per-page 隔離，避免單一 Qt process 長鏈 AV。`event_create_anomaly` 在 offscreen 點擊按鍵仍會 SEH，改為結構驗證（略過按鍵點擊）；報告 `## 結構驗證頁面` 會列出。其他頁若仍 SEH，見 `## SEH 崩潰頁面`。
- **報告輸出**：執行完畢後會產生 `scratch/button_audit_report.md` 報表，請檢視該報表以確認是否有任何按鈕拋出例外錯誤 (Exceptions)。

## 定義通過條件 (Passing Conditions)

要宣稱本技能已「通過 (Passed)」或「完成 (Done)」，必須滿足對應測試類型的通過條件：

1. **Visual Probe (視覺探針)**：
   - 探針 JSON 輸出必須包含 `visual_trustworthy: true`，且 `qss_unknown_property_warnings == 0`。
   - 命令列 exit code 必須為 `0`。
   - 必須檢查並確認下方列出的「15 維度 (15 Dimensions)」中適用的所有項目。
2. **Visual Regression (視覺回歸)**：
   - `qt_visual_regress.py` 必須明確顯示 `pass`，或是因環境不符而合法 `skip`（不允許未解釋的 `failure`）。
3. **Button Audit (動態按鍵稽核)**：
   - `scratch/button_audit_report.md` 報表中的異常數量必須為 `0`，且 orchestrator exit code 為 `0`。
   - 總覽須顯示 `隔離模式: subprocess-per-page`。
   - 若報告含 `## SEH 崩潰頁面`，視為 **not verified**。
   - `## 結構驗證頁面` 僅允許已登錄的 offscreen SEH 頁（目前 `event_create_anomaly`）；不得擴充為規避其他頁面失敗。
   - 任何拋出 Exceptions 的按鍵都必須修復完成，才可視為通過。

### 視覺審查 15 維度 (The 15 Dimensions)

A visual claim is "done" only after the relevant dimensions below are checked (skip ones that truly don't apply, and say which):

1. **Surface coverage** — every touched surface has a probe target: 6 sidebar pages (`main`, `event-list`, `master-data`, `ncr-tracker`, `stats-stress`/`ncr-stats`, `appearance-settings`), dialogs (`form-density`), exports (`pdf-export`).
2. **Multi-DPI** — `--scale 1.0,1.25,1.5`; read each PNG for badge / limit-label / disclosure clipping.
3. **Minimum width** — `--min-width` (1024×680); long CJK must not clip.
4. **Empty / loading / error states** — `--target empty-states`; confirm `暫無資料` and the NCR-unavailable placeholder render.
5. **CJK font — three sources** — JSON `cjk_font_ok` AND `ncr_cjk_font_ok` AND (for exports) `pdf_cjk_font_ok` all true.
6. **Popups / menus / tooltips** — structural assert (`toolTip()` / `accessibleName()` / menu actions), because `grab()` cannot capture them.
7. **QSS validity** — `qss_unknown_property_warnings == 0` (catches box-shadow / transition / transform / opacity etc. that Qt silently drops).
8. **Typography static audit** — no `font-weight: 500|600` in live Qt QSS (theme + ncr); single CJK font source (政策正本:`.claude/rules/visual_evidence_rules.md` §2). Pinned by tests; re-grep if you touched styling.
9. **Charts** — figure vs plot background are separate tokens (`apply_chart_surface` in `src/ui/widgets/chart_style.py`; plot uses `chart_plot_bg`); legend label colour/size readable; long CJK category labels do not overlap (read `stats-stress` / `ncr-stats` PNGs).
10. **Sidebar colour roles** — rail base, logo/footer panel, group labels, active item, active indicator, badges, primary + secondary quick actions are distinguishable (per `docs/ui-layout-theme-contract.md`).
11. **Visual regression** — `qt_visual_regress.py` passes or skips with a stated reason (never an unexplained pass).
12. **工具列按鈕完整性 (Toolbar Button Preservation)** — 確保清單工具列重置按鈕（`btn_reset`，文字為「清除」）、欄位設定切換按鈕（`column_profile_button`）、重新整理按鈕（`refresh_button`）與匯出按鈕均存在且功能正常。
13. **側欄指令導覽與無障礙標籤 (Sidebar Commands & AccessibleName)** — 側欄「系統」分組下必須包含「顯示設定」（`ACTION_OPEN_APPEARANCE_REDESIGN`），所有 `_NavButton` 必須設定 `accessibleName`。
14. **緊湊模式 0 水平滾動 (0 Horizontal Overflow)** — 表格在緊湊模式下，選用欄位隱藏，主文字欄位設為 `Stretch`，確保在標準視窗寬度（1024px）下 `horizontalScrollBar().maximum() == 0`。
15. **首頁 8 欄待辦契約 (Home Backlog 8-Column Contract)** — 首頁待辦表格必須保持 8 欄（`異常單號`、`供應商名稱`、`產品料號`、`產品品名`、`品質異常單要求`、`責任人`、`問題/摘要`、`狀態`），倉庫待處理按鈕保持「委外待處理/原物料待處理/未分流待整理」前綴，無裝飾性外層卡片。

## 何時不要觸發

- schema / migration / 匯出資料契約 → 用 `sqe-dailywork-data-contract`
- 跨層變更的路由分類(改哪裡、跑什麼) → 用 `sqe-dailywork-change-router`
- 表單欄位配對、佈局密度、工具列緊湊化或操作動線最佳化 → 用 `sqe-dailywork-ui-ux-flow-optimizer`
- 瀏覽器 / web E2E 測試不屬本技能;Playwright 在本專案也不是視覺證據(`.claude/rules/visual_evidence_rules.md` §1)
