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
- Iterate with focused tests (`$env:PYTHONPATH='src;.'; $env:QT_QPA_PLATFORM='offscreen'; .venv\Scripts\python.exe -m unittest tests.<module>`); the full suite (`-m unittest discover -s tests`) is ~279 tests and takes **20-30+ minutes** (many tests construct `MainWindow`, which boots the embedded NCR SQLite DB under offscreen Qt) — always run it backgrounded, never block on it in the foreground. The `PYTHONPATH` is required or `from ui ...` imports fail with `ModuleNotFoundError`; `scripts/verify.ps1` sets it for you.
- `scripts/qt_visual_probe.py --target main|event-create|workbench|dialog-density|form-density|stats-stress` writes native PNGs — **read the PNGs** for CJK evidence; the console prints CJK as mojibake (cp950 display artifact, not broken data). The complete target/DPI contract lives in `scripts/qt_probe_targets.json`.
- Multi-page visual review: run **one** `--target` per probe invocation (`main`, `supplier-360`, `event-list`, `home`); multiple `--target` flags may only execute the last target.
- Windows onedir build: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_windows.ps1` (runs `write_build_info.py` first; produces `dist/SQE_DailyWork/` + zip + `build-info.json`). Frozen smoke uses `--smoke-exit` with `Start-Process -Wait`; do not rely on console output from `console=False` builds.
- Full verify: `scripts/verify.ps1 -Profile Full` includes NCR tests + pytest module regressions after unittest discover; run backgrounded (~15–20 min). Evidence: `scratch/verify-full-log-final.txt`. GitHub Actions Full uses `-AllowSchemaOnlySource -SkipNativeVisual` (no formal DB in checkout; not visual evidence).
- Coverage: `scripts/verify.ps1 -Profile Coverage` (unittest + NCR + pytest modules, `scratch/coverage.xml`, baseline gate in `docs/release/coverage-baseline.json`).
- Soak: `scripts/verify.ps1 -Profile Soak` (`tests.test_stability_smoke`, default 10 cycles).
- Portable zip smoke: `scripts/portable_install_smoke.ps1` (`-UseExistingDist` after build).
