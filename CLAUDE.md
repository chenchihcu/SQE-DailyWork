@AGENTS.md

# Claude Code Adapter - SQE DailyWork

Claude Code reads this file first and imports `AGENTS.md` as the shared repo policy source. Keep this file short and Claude-specific; do not duplicate SQE DailyWork business rules here.

## Claude-Specific Notes

- Use `CLAUDE.md` as context, not as permission control. Enforced Claude behavior belongs in `.claude/settings.json`, permissions, or hooks.
- Treat `.claude/settings.local.json` as local-only preference state, not shared project policy.
- SQE DailyWork keeps its repo-local Claude automation in `.claude/settings.json`, `.claude/hooks/`, `.claude/skills/`, `.claude/agents/`, and `docs/harness/claude-code-automation.md`.
- For non-trivial changes, read `docs/harness/ai-rules-compatibility.md` before editing so tool-switching and one-writer rules stay aligned.
- For visual review, use `scripts/qt_visual_probe.py` or equivalent native Windows Qt evidence; offscreen Qt is structural-only. Pass criteria: `visual_trustworthy: true`, `cjk_font_ok: true`, `qss_unknown_property_warnings: 0`; read saved PNGs (see `AGENTS.md` UI visual closure gate).

## Verification Pointers

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/harness_check.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1
```

- Interpreter for tests / `py_compile` / probe: `.venv\Scripts\python.exe` (Python 3.14.3) — not the `.uv-python/3.12` tree.
- Iterate with focused tests (`$env:PYTHONPATH='src;.'; $env:QT_QPA_PLATFORM='offscreen'; .venv\Scripts\python.exe -m unittest tests.<module>`). Full/Coverage gates use `scripts/verify.ps1` with `Invoke-UnittestDiscoverWindowsSafe` (Windows chunked runner; never bare `unittest discover -s tests` as Full/Coverage evidence). The full suite is large and slow — always run it backgrounded, never block in the foreground. The `PYTHONPATH` is required or `from ui ...` imports fail with `ModuleNotFoundError`; `scripts/verify.ps1` sets it for you.
- Native visual targets are defined in `scripts/qt_probe_targets.json` (SSOT). Run **one** `--target` per probe invocation. Multi-page review examples: `main`, `supplier-360`, `event-list`, `manager-view` (no `home` target). UI layout changes are **not done** until the mapped target probe passes; do not defer probe to `Residual risk`.
- Windows onedir build: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_windows.ps1` (isolated staging + sanitized PATH + PyInstaller audit; writes `build-info.json` without modifying tracked source). A bounded frozen `--smoke-exit` on a scratch DB must pass before staged output is promoted to `dist/SQE_DailyWork/` + zip; `-SkipSmoke` never promotes. Do not rely on immediate console return from `console=False` builds.
- Full verify: `scripts/verify.ps1 -Profile Full` (chunked unittest + NCR + pytest + offscreen smoke + native belt + regress + harness); run backgrounded. Evidence: `scratch/verify-full-log-final.txt`. GitHub Actions Full uses `-AllowSchemaOnlySource -SkipNativeVisual` (no formal DB in checkout; not visual evidence). CI also sets `PYTHONUNBUFFERED=1`, unittest `-v`, and `SQE_TEST_HANG_SECONDS=180`; a cancelled job is not a green gate.
- Coverage: `scripts/verify.ps1 -Profile Coverage` (4-chunk unittest + NCR + pytest modules, `scratch/coverage.xml`, baseline gate in `docs/release/coverage-baseline.json`).
- Soak: `scripts/verify.ps1 -Profile Soak` (`tests.test_stability_smoke`, default 10 cycles).
- Release: `scripts/verify.ps1 -Profile Release` (harness → smoke → button audit → build → portable smoke).
- Portable zip smoke: `scripts/portable_install_smoke.ps1` (`-UseExistingDist` after build; bounded child-process timeout + non-empty smoke marker).
