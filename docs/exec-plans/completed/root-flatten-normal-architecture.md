# Root Flatten Normal Architecture - Completed

Date: 2026-06-06

## Objective

Normalize `C:\Users\user\Documents\SQE DailyWork` into the single project root.
The active app structure is now root `main.py`, `src/`, `data/`, `docs/`,
`scripts/`, and `tests/`. The former outer wrapper layer and `SQETOOL/` child
directory are retired.

## Decisions

- `SQE DailyWork` root is the only Git worktree and project root.
- Active database path is root `data/sqe_v2.db`.
- Archived NCR source database path is root `ncr/data/defect.db.migrated`.
- Normal entrypoints are root `python main.py` and `run_app.bat`.
- `run_dailywork.ps1`, `run_dailywork.bat`, `run_dailywork.vbs`, and
  `scripts/verify_all.ps1` are retired wrapper-era entrypoints.

## Pre-Move Evidence

- Original Git root: `C:/Users/user/Documents/SQE DailyWork/SQETOOL`.
- Original tracked status: clean before the move.
- Pre-root-flatten backup: `data_backups/pre-root-flatten-20260606-211649`.
- Current-root DB backup run: `data_backups/20260606-211649`.
- Pre-move `data/sqe_v2.db` source hash:
  `07324B269332A332152FA4500CD4A6B57B867AB6EF35E89BD8144DE731D4AFF8`
  (`282624` bytes).
- Pre-move archived NCR DB source hash:
  `5951948E72448E1573365CAC30BCC815A2E630F57804A87FF9FB05E807417ED2`
  (`53248` bytes).

## Completed Changes

- Moved the child `.git` directory and all project source/runtime folders from
  `SQETOOL/` into the root.
- Removed the now-empty `SQETOOL/` directory.
- Preserved the retired outer wrapper plan as
  `docs/exec-plans/completed/retired-root-wrapper-phase-3-unified-software-entrypoint.md`.
- Added `scripts/backup_data.ps1` for root `data/sqe_v2.db` backups.
- Updated repo policy, README, architecture contract, source baseline manifest,
  command policy, Cursor/Antigravity/Claude adapters, and NCR module docs for
  root-as-project paths.
- Added `data_backups/` to `.gitignore`.

## Verification

Completed:

- `C:\Program Files\Git\cmd\git.exe rev-parse --show-toplevel` returned
  `C:/Users/user/Documents/SQE DailyWork`.
- Path guard passed: the former child project directory, `src/data/sqe_v2.db`,
  and `src/ncr/data/defect.db` do not exist.
- `database.connection.DB_PATH` resolves to root `data/sqe_v2.db`.
- DB row-count guard passed after the move and after full verification:
  `suppliers=28`, `products=88`, `anomalies=22`, `visits=7`,
  `visit_defect_notes=0`, `defect_records=15`.
- New root backup script passed:
  `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\backup_data.ps1`.
- Full gate passed:
  `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1`.
- Tracked live-file stale reference scan passed after excluding retired
  historical execution plans.

Notes:

- Pre-move `data/sqe_v2.db` hash was
  `07324B269332A332152FA4500CD4A6B57B867AB6EF35E89BD8144DE731D4AFF8`.
- Post-verify `data/sqe_v2.db` hash was
  `3D197B0F352CFBD06D4C92809FCF94F17E273AEA458CE53B4BE18292B3FDF6EE`.
  Row counts stayed stable.
- Archived NCR DB hash remained
  `5951948E72448E1573365CAC30BCC815A2E630F57804A87FF9FB05E807417ED2`.
- `scripts\verify.ps1` emitted existing SQLite `ResourceWarning` messages during
  unittest execution, but all 279 tests passed and the full gate exited 0.

## Rollback

If a required verification gate fails and cannot be repaired in place, stop and
restore from `data_backups/pre-root-flatten-20260606-211649`:

1. Move root project content back into `SQETOOL/`, including `.git`.
2. Restore root wrapper files from
   `data_backups/pre-root-flatten-20260606-211649/root-wrapper-files/`.
3. Restore DB files from the pre-root-flatten or current-root DB backups.
4. Verify from the old boundary with
   `C:\Program Files\Git\cmd\git.exe -C SQETOOL status --short` and the old root
   `scripts\verify_all.ps1` if restored.
