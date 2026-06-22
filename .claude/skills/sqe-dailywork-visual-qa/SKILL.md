---
name: sqe-dailywork-visual-qa
description: 用於 SQE DailyWork 的 PySide6 UI、截圖、中文(CJK)文字渲染、字體排版、間距與視覺審查;需要原生 Windows Qt 的視覺證據。Use this skill 當要做 UI 視覺檢查或截圖分析時。觸發詞包含「PySide6」「UI」「截圖」「screenshot」「CJK」「中文渲染」「typography」「視覺審查」「visual QA」。
allowed-tools: Read, Grep, Glob, Bash
---

# SQE DailyWork Visual QA

Use this skill for UI, layout, theme, screenshot, CJK text, typography, tab, widget, and visual-polish tasks on the PySide6 desktop app.

For a broad multi-surface sweep (main shell + forms + every stats page), delegate to the `sqe-dailywork-qt-visual-reviewer` subagent. Use this skill for inline, single-surface checks while editing.

**Visual QA is not just "take a screenshot."** A `widget.grab()` PNG only proves the main Qt widget tree, at one DPI, in its default state, with populated data. The checklist below exists because everything outside that — other DPIs, empty/error states, minimum width, popups/menus/tooltips, the NCR module's own font, the PDF export font, and silently-failing QSS — does not show up in a single happy-path screenshot.

## Required Context

- Read `AGENTS.md`, `.cursor/rules/agents_gateway.mdc`, `docs/harness/README.md`, and the target `src/ui/` file.
- Before adding any styling, check `src/ui/theme.py` and `src/ui/layout_constants.py` and reuse shared widgets. Prefer QSS `role` / `variant` and theme tokens over per-widget `setStyleSheet` (AGENTS.md §3–4). Pull layout values from `src/ui/layout_constants.py` (`FORM_MAX_WIDTH`, `GRID_GUTTER`, `ROW_GAP`, `PANEL_MARGINS`) instead of hardcoding pixels — those constants are the single source of truth (pinned by `tests/test_layout_constants.py`).
- The shell is a `SidebarNav` + `QStackedWidget` architecture, NOT a tab bar. Preserve the sidebar information architecture (首頁 / 事件管理 / 異常事件統計 / 不合格品 / 不合格品統計分析 / 基礎資料); the former anomaly / visit / closed lists are now scope tabs inside the consolidated 事件管理 page (see `src/ui/main_window.py` and `README.md`). Keep the home screen operational (no hero/cover panels). Keep SQE DailyWork terminology aligned with `README.md` and `src/ui/popup_i18n.py`.
- **Single font source of truth:** the CJK font fallback chain lives only in `src/ui/theme.py` (`PREFERRED_CJK_FONT_FAMILIES` / `CJK_FONT_FAMILY_CSS`); `src/ncr/ui/ui_style.py` imports it. Do not reintroduce a second list. Live Qt QSS must use only `font-weight` 400 / 700 — never 500 / 600 (Windows renders CJK inconsistently at medium weights). Both rules are pinned by `tests/test_font_source_single_truth.py` and `tests/test_theme_typography_consistency.py`.

## Visual Evidence Rule

- `QT_QPA_PLATFORM=offscreen` is structural smoke only — never visual evidence (it can miss Windows CJK fonts and render 方框).
- Visual screenshots, CJK rendering, font, and typography judgments must use native Windows Qt via `scripts\qt_visual_probe.py` (it auto-forces `QT_QPA_PLATFORM=windows` on Windows).
- **Read the PNG, not the console.** The probe prints CJK to the console as cp950 mojibake — that is a display artifact, NOT broken data. Judge CJK only from the saved PNG.
- **`grab()` cannot capture top-level popups.** `QMenu` (e.g. the event action menu), `QComboBox` dropdown lists, and tooltips render as separate native surfaces that a parent-widget `grab()` does not include. Verify those with a **structural assert** (e.g. `widget.toolTip()` / `accessibleName()` is set for elided cells, menu actions exist), not a screenshot.
- Playwright is not visual evidence for this PySide6 desktop app — nor are any browser/web tools.

## Running the probe

Interpreter: `.venv\Scripts\python.exe` (Python 3.14.3) — not the `.uv-python/3.12` tree.

```
.venv\Scripts\python.exe scripts\qt_visual_probe.py --target main --output Outputs\visual_qa\probe.png
```

- `--target` covers every surface family. Non-`main` targets write several suffixed PNGs:
  - `main` — shell (lands on the 事件管理 page) · `form-density` — visit / supplier / product / warehouse / quick-product dialogs
  - `event-list` — consolidated 事件管理 table, long-CJK stress, all 4 scope tabs · `master-data` — 供應商 / 產品 master tables
  - `ncr-tracker` — warehouse 建立 / 待處理 / 歷史 tabs (list views, not just the create form)
  - `stats-stress` — 4 異常統計 charts with long-name stress · `ncr-stats` — NCR 2×2 grid
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

## Verification — the 11 dimensions

A visual claim is "done" only after the relevant dimensions below are checked (skip ones that truly don't apply, and say which):

1. **Surface coverage** — every touched surface has a probe target: 6 sidebar pages (`main`, `event-list`, `master-data`, `ncr-tracker`, `stats-stress`/`ncr-stats`), dialogs (`form-density`), exports (`pdf-export`).
2. **Multi-DPI** — `--scale 1.0,1.25,1.5`; read each PNG for badge / limit-label / disclosure clipping (§11).
3. **Minimum width** — `--min-width` (1024×680); long CJK must not clip.
4. **Empty / loading / error states** — `--target empty-states`; confirm `暫無資料` and the NCR-unavailable placeholder render.
5. **CJK font — three sources** — JSON `cjk_font_ok` AND `ncr_cjk_font_ok` AND (for exports) `pdf_cjk_font_ok` all true.
6. **Popups / menus / tooltips** — structural assert (`toolTip()` / `accessibleName()` / menu actions), because `grab()` cannot capture them.
7. **QSS validity** — `qss_unknown_property_warnings == 0` (catches box-shadow / transition / transform / opacity etc. that Qt silently drops).
8. **Typography static audit** — no `font-weight: 500|600` in live Qt QSS (theme + ncr); single CJK font source. Pinned by tests; re-grep if you touched styling.
9. **Charts (§10)** — figure vs plot background are separate tokens (`apply_chart_surface` in `src/ui/widgets/chart_style.py`; plot uses `chart_plot_bg`); legend label colour/size readable; long CJK category labels do not overlap (read `stats-stress` / `ncr-stats` PNGs).
10. **Sidebar colour roles** — rail base, logo/footer panel, group labels, active item, active indicator, badges, primary + secondary quick actions are distinguishable (per `docs/ui-layout-theme-contract.md`).
11. **Visual regression** — `qt_visual_regress.py` passes or skips with a stated reason (never an unexplained pass).

- Structural UI behavior (startup, widget existence, signal wiring): focused unittest or offscreen smoke is acceptable, but label it structural.
- Always include the screenshot path(s) and the probe JSON (`visual_trustworthy` / `cjk_font_ok` / `ncr_cjk_font_ok` / `qss_unknown_property_warnings`) in the final verification summary. If native Qt is genuinely unavailable, say so and downgrade the claim to structural — do not pass off offscreen output as visual evidence.
