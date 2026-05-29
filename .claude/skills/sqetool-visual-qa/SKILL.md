---
name: sqetool-visual-qa
description: Use for SQETOOL PySide6 UI, screenshots, Chinese text rendering, typography, spacing, and visual review; requires native Qt visual evidence.
allowed-tools: Read, Grep, Glob, Bash
---

# SQETOOL Visual QA

Use this skill for UI, layout, theme, screenshot, CJK text, typography, tab, widget, and visual polish tasks.

## Required Context

- Read `AGENTS.md`, `.cursorrules`, `docs/harness/README.md`, and the target `ui/` file.
- Check `ui/theme.py`, `ui/layout_constants.py`, and shared widgets before adding ad-hoc styling.
- Preserve the seven-tab workflow and SQETOOL terminology from `README.md`.

## Visual Evidence Rule

- `QT_QPA_PLATFORM=offscreen` is structural smoke only.
- Visual screenshots, Chinese text rendering, font checks, and typography judgment must use native Windows Qt through `scripts\qt_visual_probe.py` or an equivalent native-platform capture.
- Playwright is not visual evidence for this PySide6 desktop app.

## Verification

- For visual claims, run `.venv\Scripts\python.exe scripts\qt_visual_probe.py` or report why native Qt is unavailable.
- For structural UI behavior, focused unittest or offscreen smoke is acceptable, but label it as structural evidence.
- Include the screenshot path or probe JSON result in the final verification summary.
