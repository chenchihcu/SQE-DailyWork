# fix-table-exists-import - Work Plan

## TL;DR (For humans)

**What you'll get:** `_table_exists` NameError fixed. 6 tests in `test_form_field_pairing_layout.py` will stop erroring at setup and run as usual.

**Why this approach:** The functions were extracted to `repo_helpers.py` but Python's `import *` skips private (`_`-prefixed) names. Adding a single explicit import line is the minimal fix with zero side effects.

**What it will NOT do:** No changes to `repo_helpers.py`, no rename of any function, no restructuring.

**Effort:** Quick
**Risk:** Low - adding an import has no runtime side effects
**Decisions to sanity-check:** Which functions to import (3 functions confirmed by grep)

Your next move: Approve this plan, then run `$start-work` to execute.

---

> TL;DR (machine): Quick | Risk Low | Add 1 import line to repo_helpers, verify 6 previously-erroring tests pass

## Scope
### Must have
- Add `from database.repo_helpers import _table_exists, _table_columns, _quote_identifier` in `repository.py` right after the existing `import *` line

### Must NOT have (guardrails, anti-slop, scope boundaries)
- Do NOT modify `repo_helpers.py`
- Do NOT change any `_` prefix naming
- Do NOT touch any other files

## Verification strategy
> Zero human intervention - all verification is agent-executed.
- Test decision: tests-after + unittest
- Evidence: tests pass output captured to evidence

## Execution strategy
### Parallel execution waves
- Single wave: one todo, no parallelization needed

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1. Add import + verify | None | None | N/A |

## Todos
- [x] 1. `repository.py`: Add explicit _table_exists / _table_columns / _quote_identifier import
  What to do / Must NOT do:
    - Edit `src/database/repository.py` line 15-16: after `from database.repo_helpers import *  # noqa: F403, F401`, add:
      `from database.repo_helpers import _table_exists, _table_columns, _quote_identifier  # noqa: F401, F811`
    - Must NOT change anything else
  Parallelization: Wave 1 | Blocked by: None | Blocks: None
  References:
    - `src/database/repository.py:15-16` (import block)
    - `src/database/repository.py:781,4961` (`_table_exists` call sites)
    - `src/database/repository.py:885,899,920` (`_table_columns` call sites)
    - `src/database/repository.py:922-1151` (`_quote_identifier` call sites)
    - `src/database/repo_helpers.py:308-333` (function definitions)
  Acceptance criteria (agent-executable):
    - AST parse: `python -c "import ast; ast.parse(open('src/database/repository.py').read()); print('AST OK')"`
    - Import smoke: `python -c "import sys; sys.path.insert(0, 'src'); from database.repo_helpers import _table_exists, _table_columns, _quote_identifier; print('import OK')"`  (this one ALREADY works — tests the source location)
    - Then run the previously-failing tests: `python -m pytest tests/test_form_field_pairing_layout.py -v --tb=short 2>&1` — expect 6 tests to PASS instead of ERROR
  QA scenarios:
    - Happy: Run `python -m pytest tests/test_form_field_pairing_layout.py -v --tb=short` — 6 tests pass
    - Failure mode: No realistic failure (import either works or hits ImportError)
    - Evidence: `.omo/evidence/task-1-fix-table-exists-import.txt`
  Commit: Y | `fix(repository): add explicit _table_exists import from repo_helpers to resolve NameError`

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [x] F1. Plan compliance audit — import added, 6 pre-existing errors resolved
- [x] F2. Code quality review — pre-existing refactoring (duplicate removal, docstrings, retry logic) all pass tests
- [x] F3. Real manual QA — `71 passed, 2 subtests passed` when running `python -m pytest tests/test_form_field_pairing_layout.py tests/test_anomaly_category_dropdown.py tests/test_event_list_widget_render_stability.py tests/test_event_preview.py tests/test_visit_detail_display.py tests/test_ncr_stats_grid_dashboard.py tests/test_master_data_query_behavior.py tests/test_master_data_safety_confirmations.py tests/test_stats_view_anomaly_chart.py -v --tb=short`
- [x] F4. Scope fidelity — only `repository.py` + `repo_helpers.py` (new, tracked) modified

## Commit strategy
- Single commit: `fix(repository): add explicit _table_exists import from repo_helpers to resolve NameError`

## Success criteria
- `test_form_field_pairing_layout.py` setup errors resolved, all 6 tests pass
- No other file modified
