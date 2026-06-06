# Exec Plan — Restructure source folders into a formal `src/` layout

## Goal

Move the application source packages into a single `src/` root so the repo matches
a formal Python project layout, **without** breaking imports, entry points, the
live SQLite databases, or the multi-assistant governance contracts. Execution is
**deferred**: this plan is authored now and run later as an isolated, reviewable
step on a clean working tree.

Done-state: `git mv`-based move with history preserved; `scripts/verify.ps1` and
the full `python -m unittest discover -s tests` (279 tests) green; the app boots
natively and reads the **same** `data/sqe_v2.db` (no orphaned/empty DB created);
governance docs updated.

## Decisions

- **Defer execution** until the current KPI-overdue + sidebar-icon work *and*
  Codex's in-flight diff are committed. Restructure on a clean tree (or a
  dedicated worktree/branch) — one writer per checkout (AGENTS.md §8). A 100-file
  move layered on the current noisy tree would be unreviewable and risks a Codex
  collision.
- **Recommended flavor: flat `src/`** (`src/database/`, `src/services/`,
  `src/ui/`, `src/ncr/`) with `pythonpath = src`. The 243 import lines across 102
  files stay unchanged (`from ui...`, `from database...` still resolve). Lowest
  risk, contract-aligned.
- **Namespaced `src/sqetool/` package** is documented as an alternative; it is the
  most "formal" but rewrites all 243 imports and is higher risk. Choose only if a
  real top-level namespace is required.
- **Runtime data stays at repo root.** `data/sqe_v2.db`, `data/sqe.db`, and the
  NCR DB are gitignored runtime state; they must not move into `src/`. Every
  moved module that derives a repo-root path from `Path(__file__)` must be
  repointed so these paths are unchanged.

## Critical risk — data-path landmine (must fix during the move)

`src/.../database/connection.py` currently does:

```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent   # == repo root today
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "sqe_v2.db"
...
ncr_db = PROJECT_ROOT / "ncr" / "data" / "defect.db"     # line ~99
```

After moving `database/` into `src/`, `parent.parent` becomes `<root>/src`, so the
app would create a **new empty** `<root>/src/data/sqe_v2.db` and ignore the user's
real database. Every `Path(__file__)`-anchored path in a moved module must be
audited and fixed. Known sites (from scan):
`database/connection.py`, `services/event_pdf_exporter.py`, `services/report_service.py`,
`ncr/services/export_service.py`, `ncr/ui/defect_list.py`, `ncr/ui/ui_style.py`,
`ui/theme.py` (`asset_path` is module-relative → survives the move).
Modules that stay at root (`main.py`, `run_mig.py`, `scripts/*`, `tests/*`) keep
their anchors but must add `src` to `sys.path`.

## Verification (run after execution)

1. `git status` clean before starting; commit the move as its own commit.
2. `python -m py_compile` across `src/` (all modules).
3. `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1`.
4. Full suite: `python -m unittest discover -s tests` → 279 OK.
5. **DB-path guard:** launch `python scripts/qt_visual_probe.py --target main`
   (native), confirm the app boots, and assert `<root>/data/sqe_v2.db` is the file
   actually opened (mtime/row counts unchanged) and that **no** `src/data/` or
   `src/ncr/data/` DB was created.
6. `run_app.bat` still launches the app.

## Remaining work (the mechanical procedure — flat `src/`)

1. **Preconditions:** land current work; `git status --short` clean; create a
   branch/worktree.
2. **Move (history-preserving):** `mkdir src` then
   `git mv database services ui ncr src/`.
3. **Fix path anchors** (the landmine): in each moved module that computes a
   repo-root path, add one parent level (e.g. `connection.py`:
   `Path(__file__).resolve().parents[2]`) and re-decide each runtime path so
   `data/` stays at repo root and the NCR DB resolves to its intended location.
   Audit every site listed above.
4. **Entry points / path config:**
   - `pytest.ini`: `pythonpath = .` → `pythonpath = src`.
   - `main.py:7`: `Path(__file__).resolve().parent` → `... / "src"` on `sys.path`.
   - `run_mig.py`, `scripts/*.py` (e.g. `qt_visual_probe.py` `REPO_ROOT`),
     `run_app.bat`: insert `<root>/src` on the path.
   - Optional: add `pyproject.toml` with `[tool.pytest.ini_options] pythonpath=["src"]`
     to formalize.
5. **Update structural references:** `tests/test_surface_usage_structure.py` and
   any test/script asserting folder paths; `scripts/verify.ps1`/`harness_check.ps1`
   if they hardcode source paths.
6. **Governance/doc sync (AGENTS.md mandate):** `AGENTS.md` knowledge map,
   `docs/architecture-workflow-contract.md` ("UI Entrypoint And Folder Boundaries"
   → source folders now under `src/`), `docs/harness/source-baseline-manifest.md`,
   `.codex/rules/project.rules`, `.cursor/rules/agents_gateway.mdc`, `CLAUDE.md`,
   `README.md`.
7. **Verify** per the Verification section; only then move this plan to
   `docs/exec-plans/completed/`.

### Namespaced `src/sqetool/` variant (alternative, higher risk)

Same as above, plus: `git mv` packages under `src/sqetool/`, add
`src/sqetool/__init__.py`, and rewrite all 243 imports (`from database` →
`from sqetool.database`, etc.) — including in-function dynamic imports
(`database.migration`, `database.ncr_migration`, `database.repository`) and the
`ncr/` package's internal imports. Gate strictly on the full suite.

## Progress

- 2026-06-06: Plan authored. Import surface measured (243 lines / 102 files),
  data-path landmine identified. **Execution not started** (deferred by decision).
