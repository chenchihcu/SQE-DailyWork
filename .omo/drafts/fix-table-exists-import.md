---
slug: fix-table-exists-import
status: awaiting-approval
intent: clear
pending-action: write .omo/plans/fix-table-exists-import.md
approach: Add explicit imports in repository.py for _-prefixed functions extracted to repo_helpers.py
---

# Draft: fix-table-exists-import

## Components (topology ledger)
| id | outcome | status | evidence path |
|---|---|---|---|
| 1. Add explicit imports | `_table_exists`, `_table_columns`, `_quote_identifier` available in repository.py | active | tests pass |

## Open assumptions (announced defaults)
| assumption | adopted default | rationale | reversible? |
|---|---|---|---|
| Only 3 functions need explicit import | Grep confirms only these 3 are called from repository.py with `_` prefix | Git grep of `_table_exists`, `_table_columns`, `_quote_identifier` in repository.py | Yes |

## Findings (cited - path:lines)
- `repository.py:15` imports `from database.repo_helpers import *` — Python `import *` skips names starting with `_`
- `repository.py:781` calls `_table_exists(conn, "migration_meta")` — NameError at runtime
- `repository.py:4961` calls `_table_exists(conn, "visit_product_sections")` — NameError at runtime
- `repository.py:885,899,920` calls `_table_columns(conn, ...)` — NameError at runtime
- `repository.py:922,930,931,933,935,1002,1003,1015,1016,1051,1068-1075,1103-1104,1128-1129,1151` all call `_quote_identifier(...)` — NameError at runtime
- `repo_helpers.py:308-318` defines `_table_exists`
- `repo_helpers.py:321-327` defines `_table_columns`
- `repo_helpers.py:330-333` defines `_quote_identifier`

## Decisions (with rationale)
**Decision**: Add explicit imports after the existing `import *` line rather than removing the `_` prefix
- Rationale: Removing `_` would shadow `table_columns` local variable at line 920 (`table_columns = _table_columns(conn, table_name)`) and is a broader API change. Explicit import is minimal and targeted.

## Scope IN
- Add 1 import line to `src/database/repository.py`
- Run `test_form_field_pairing_layout.py` to verify fix
- Commit

## Scope OUT (Must NOT have)
- Do NOT modify `repo_helpers.py`
- Do NOT change the `_` prefix convention
- Do NOT touch any other files

## Open questions
None — intent is clear, RCAs are complete.

## Approval gate
status: awaiting-approval
<!-- When exploration is exhausted and unknowns are answered, set status: awaiting-approval. -->
<!-- That durable record is the loop guard: on a later turn read it and resume at the gate instead of re-running exploration. -->
