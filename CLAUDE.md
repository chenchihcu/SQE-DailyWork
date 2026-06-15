@AGENTS.md

# Claude Code Adapter - SQE DailyWork

Claude Code reads this file first and imports `AGENTS.md` as the shared repo policy source. Keep this file short and Claude-specific; do not duplicate SQE DailyWork business rules here.

## Claude-Specific Notes

- Use `CLAUDE.md` as context, not as permission control. Enforced Claude behavior belongs in `.claude/settings.json`, permissions, or hooks.
- Treat `.claude/settings.local.json` as local-only preference state, not shared project policy.
- SQE DailyWork keeps its repo-local Claude automation in `.claude/settings.json`, `.claude/hooks/`, `.claude/skills/`, `.claude/agents/`, and `docs/harness/claude-code-automation.md`.
- For non-trivial changes, read `docs/harness/ai-rules-compatibility.md` before editing so tool-switching and one-writer rules stay aligned.
- For visual review, use `scripts/qt_visual_probe.py` or equivalent native Windows Qt evidence; offscreen Qt is structural-only.

## Verification Pointers

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/harness_check.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1
```

- Interpreter for tests / `py_compile` / probe: `.venv\Scripts\python.exe` (Python 3.14.3) — not the `.uv-python/3.12` tree.
- Iterate with focused tests (`$env:PYTHONPATH='src;.'; $env:QT_QPA_PLATFORM='offscreen'; .venv\Scripts\python.exe -m unittest tests.<module>`); the full suite (`-m unittest discover -s tests`) is ~279 tests / several minutes. The `PYTHONPATH` is required or `from ui ...` imports fail with `ModuleNotFoundError`; `scripts/verify.ps1` sets it for you.
- `scripts/qt_visual_probe.py --target main|form-density|stats-stress` writes a native PNG — **read the PNG** for CJK evidence; the console prints CJK as mojibake (cp950 display artifact, not broken data).
