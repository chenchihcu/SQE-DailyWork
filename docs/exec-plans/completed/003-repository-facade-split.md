# 003# repository.py Facade Split

Plan status: completed

## Goal

Split the ~7756-line [`src/database/repository.py`](../../src/database/repository.py) into seven domain modules plus a backward-compatible facade. Preserve all public import paths, SQL/migration behavior, and supplier-event vs warehouse NCR data-line boundaries.

## Decisions

- Callers keep `from database.repository import …`; no service/test import rewrites in this rollout.
- Mechanical move only: no DDL, CHECK, migration_meta key, Promotion Gate, or ValueError copy changes.
- Existing satellite repos (`case_action_repository`, `anomaly_hypothesis_repository`, `anomaly_repeat_repository`) stay as-is; facade continues aliasing them.
- Submodules must not import `database.repository` at module import time except via lazy helpers for `refresh_monthly_cache` patch compatibility.
- No writes to formal `data/sqe_v2.db`.

## Progress

- [x] Wave 1: `schema_bootstrap.py`
- [x] Wave 2: `visit_legacy_repository.py`
- [x] Wave 3: `supplier_repository.py` + `product_repository.py`
- [x] Wave 4: `anomaly_repository.py` + `anomaly_workbench_repository.py`
- [x] Wave 5: `event_query_repository.py`
- [x] Wave 6: thin `repository.py` facade + `test_repository_facade.py` + harness/docs

## Verification

- Focused unittest bundle: 117 OK (`migration`, `visit`, `master data`, `anomaly`, `attachments`, `trace`, `global_search`, `event_scope`, `monthly_stats`, `architecture_workflow_contract`).
- `tests/test_repository_facade.py`
- `py_compile` on all split modules
- `scripts/harness_check.ps1` PASS
- Background `scripts/verify.ps1` (pending re-run after facade compat fix)

## Remaining work

None for repo-local split. Confirm full verify when background job completes.
