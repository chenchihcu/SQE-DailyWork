---
name: sqe-dailywork-visual-qa
description: Use for SQE DailyWork PySide6 UI, screenshots, Chinese (CJK) text rendering, typography, spacing, and visual review; requires native Windows Qt visual evidence.
allowed-tools: Read, Grep, Glob, Bash
---

# SQE DailyWork Visual QA

Use this skill for UI, layout, theme, screenshot, CJK text, typography, tab, widget, and visual-polish tasks on the PySide6 desktop app.

For a broad multi-surface sweep (main shell + forms + every stats page), delegate to the `sqe-dailywork-qt-visual-reviewer` subagent. Use this skill for inline, single-surface checks while editing.

## Required Context

- Read `AGENTS.md`, `.cursor/rules/agents_gateway.mdc`, `docs/harness/README.md`, and the target `src/ui/` file.
- Before adding any styling, check `src/ui/theme.py` and `src/ui/layout_constants.py` and reuse shared widgets. Prefer QSS `role` / `variant` and theme tokens over per-widget `setStyleSheet` (AGENTS.md §3–4). Pull layout values from `src/ui/layout_constants.py` (`FORM_MAX_WIDTH`, `GRID_GUTTER`, `ROW_GAP`, `PANEL_MARGINS`) instead of hardcoding pixels — those constants are the single source of truth (pinned by `tests/test_layout_constants.py`).
- The shell is a `SidebarNav` + `QStackedWidget` architecture, NOT a tab bar. Preserve the sidebar information architecture (首頁 / 事件管理 / 異常事件統計 / 不合格品 / 不合格品統計分析 / 基礎資料); the former anomaly / visit / closed lists are now scope tabs inside the consolidated 事件管理 page (see `src/ui/main_window.py` and `README.md`). Keep the home screen operational (no hero/cover panels). Keep SQE DailyWork terminology aligned with `README.md` and `src/ui/popup_i18n.py`.

## Visual Evidence Rule

- `QT_QPA_PLATFORM=offscreen` is structural smoke only — never visual evidence (it can miss Windows CJK fonts and render 方框).
- Visual screenshots, CJK rendering, font, and typography judgments must use native Windows Qt via `scripts\qt_visual_probe.py` (it auto-forces `QT_QPA_PLATFORM=windows` on Windows).
- **Read the PNG, not the console.** The probe prints CJK to the console as cp950 mojibake — that is a display artifact, NOT broken data. Judge CJK only from the saved PNG.
- Playwright is not visual evidence for this PySide6 desktop app — nor are any browser/web tools.

## Running the probe

Interpreter: `.venv\Scripts\python.exe` (Python 3.14.3) — not the `.uv-python/3.12` tree.

```
.venv\Scripts\python.exe scripts\qt_visual_probe.py --target main --output Outputs\visual_qa\probe.png
```

- `--target`: `main` (shell) | `form-density` (visit / supplier / product / warehouse / quick-product forms) | `stats-stress` (4 stats tabs with long-name stress data) | `ncr-stats` (NCR 2×2 grid). Non-`main` targets write several suffixed PNGs (e.g. `_visit-form`, `_stats-trend`).
- Default output is the OS temp dir; pass `--output Outputs\...` so artifacts land under `Outputs/` per repo convention.
- `--allow-offscreen` / `--no-screenshot` are for structural-only runs; label any such evidence as structural.

The probe is self-checking — read its JSON, do not eyeball platform validity:

- `visual_trustworthy: true` (native platform AND a CJK-capable font) is required before any visual claim.
- Also check `cjk_font_ok`, `qt_platform`, and `selected_font`.
- Exit codes: `0` ok · `2` refused offscreen for a visual run · `3` not visual-trustworthy. A non-zero exit means your screenshot is NOT valid visual evidence.

## Verification

- Visual claims: run the probe, confirm `visual_trustworthy: true`, and read the PNG. If native Qt is genuinely unavailable, say so and downgrade the claim to structural — do not pass off offscreen output as visual evidence.
- Structural UI behavior (startup, widget existence, signal wiring): focused unittest or offscreen smoke is acceptable, but label it structural.
- Always include the screenshot path(s) and the probe JSON (`visual_trustworthy` / `cjk_font_ok`) in the final verification summary.
