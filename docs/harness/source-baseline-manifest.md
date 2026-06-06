# Source Baseline Manifest - SQE DailyWork

Last inspected: 2026-06-06

## Purpose

This manifest records the local Git boundary for AI-agent handoff. It does not
stage, commit, delete, or approve files. It identifies which source surfaces are
reviewed project state and which generated/runtime surfaces must stay outside
the source baseline.

Claim types used here: `local-observed`, `audit-inference`, `assumption`, `not verified`.

## Inspection Commands

| Claim | Type | Command or source |
| --- | --- | --- |
| Git root and tracked files | `local-observed` | `C:\Program Files\Git\cmd\git.exe rev-parse --show-toplevel`; `C:\Program Files\Git\cmd\git.exe ls-files` |
| Working tree status | `local-observed` | `C:\Program Files\Git\cmd\git.exe status --short --untracked-files=all` |
| Ignored file surface | `local-observed` | `C:\Program Files\Git\cmd\git.exe status --short --ignored` |
| Governance file presence | `local-observed` | `Test-Path` checks for `AGENTS.md`, `CLAUDE.md`, `.agents/rules`, `.cursor/rules`, `.codex/rules`, and `scripts/harness_check.ps1` |

## Git Boundary Summary

| Field | Type | Value |
| --- | --- | --- |
| Repository path | `local-observed` | `C:\Users\user\Documents\SQE DailyWork` |
| Git root | `local-observed` | `C:/Users/user/Documents/SQE DailyWork` |
| Tracked files before staging root-flatten additions | `local-observed` | `180` |
| Source additions after root flatten | `audit-inference` | `scripts/backup_data.ps1`; root-flatten completion docs; retired root-wrapper history doc |
| Ignored runtime/generated entries after root flatten | `local-observed` | `data/`, `ncr/data/`, `data_backups/`, local runtimes, caches, outputs |
| `source_baseline_status` | `audit-inference` | `verified: root project layout checkpoint after full verification` |
| Current writer mode | `audit-inference` | `single writer per worktree unless a new complex change starts` |

## Tracked / Untracked / Ignored Summary

| Group | Type | Observed examples | Baseline meaning |
| --- | --- | --- | --- |
| Tracked source | `audit-inference` | `main.py`, `src/database/`, `src/services/`, `src/ui/`, `src/ncr/`, `tests/`, `scripts/`, `docs/`, governance rules | Reviewed source surface for the root project layout. |
| Embedded NCR source | `audit-inference` | `src/ncr/embed.py`, `src/ncr/db/`, `src/ncr/models/`, `src/ncr/services/`, `src/ncr/ui/`, `src/ncr/tests/`, `src/ncr/README.md` | Keep as the embedded warehouse nonconforming-product workflow. |
| Removed NCR residue | `audit-inference` | `ncr/.github/`, `ncr/.gitignore`, `ncr/.ruff.toml`, one-off logs, probe PNGs, standalone review/skill notes | Standalone project residue; not part of the embedded workflow baseline. |
| Ignored runtime/generated | `local-observed` | `data/`, `ncr/data/`, `Outputs/`, `scratch/`, `build/`, `dist/`, caches, local runtimes, `import_err.txt` | Must not be captured by blind staging. |
| Local-only tool state | `local-observed` | `.claude/settings.local.json`, `.claude/worktrees/`, `.playwright-mcp/` logs | Keep local-only; do not use as shared policy. |

## File Classification

| List | Type | Items |
| --- | --- | --- |
| `recommended-track-list` | `audit-inference` | `AGENTS.md`, `CLAUDE.md`, `.gitignore`, `.editorconfig`, `pytest.ini`, `requirements.txt`, `README.md`, `main.py`, `run_app.bat`, `run_mig.py`, `src/database/**/*.py`, `src/services/**/*.py`, `src/services/assets/*.png`, `src/ui/**/*.py`, `src/ui/assets/**/*.svg`, `tests/**/*.py`, `scripts/*.py`, `scripts/*.ps1`, `docs/**/*.md`, `src/ncr/**/*.py`, `src/ncr/**/*.md`, `src/ncr/ui/assets/*.svg`, `.agents/rules/**`, `.cursor/rules/**`, `.codex/rules/**`, `.claude/settings.json`, `.claude/hooks/**`, `.claude/skills/**`, `.claude/agents/**` |
| `recommended-ignore-list` | `audit-inference` | `.env`, `.venv/`, `.uv-cache/`, `.uv-python/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `data/`, `ncr/data/`, `data_backups/`, `Outputs/`, `scratch/`, `build/`, `dist/`, `*.log`, `*.tmp`, `import_err.txt`, `.claude/settings.local.json`, `.claude/worktrees/`, `.playwright-mcp/` |
| `needs-user-decision-list` | `audit-inference` | Data-mutating scripts before execution: `run_mig.py`, `scripts/migrate_to_v2.py`, `scripts/recode_anomaly_no_all_dbs.py`, `scripts/migrate_ncr_defects_to_main_db.py` |
| `do-not-track-list` | `audit-inference` | Runtime DBs, generated outputs, build/dist artifacts, caches, scratch folders, import error captures, local-only assistant settings, worktree folders |

## Suspicious Items

| Item | Type | Finding | Action |
| --- | --- | --- | --- |
| Runtime DB path drift | `audit-inference` | Source packages live under `src/`, while runtime DBs stay under repo-root `data/` and ignored root `ncr/data/`. | Keep `database.connection.PROJECT_ROOT` anchored to repo root and verify no `src/data/` DB appears. |
| Scratch/generated state | `local-observed` | `scratch/`, `Outputs/`, runtime DBs, caches, and local runtimes remain ignored as generated local state. | Keep ignored; do not stage blindly. |
| Data-mutating scripts | `audit-inference` | Migration/recode scripts are source, but execution can mutate local data. | Track source after review; run only through approved verification or migration plans. |

## Baseline Commit Readiness

| Gate | Type | Status |
| --- | --- | --- |
| Git root exists | `local-observed` | `pass: root is C:/Users/user/Documents/SQE DailyWork` |
| Governance files are visible to Git | `local-observed` | `pass` |
| Generated/runtime files are ignored | `local-observed` | `pass with residual risk` |
| Reviewed source baseline exists | `audit-inference` | `pass after root-flatten normalization checkpoint` |
| Scratch/generated state excluded | `local-observed` | `pass with residual risk` |
| Worktree automation readiness | `audit-inference` | `pass after root-flatten normalization and verification complete` |

## Role Review Simulation

| Role | Result | Basis |
| --- | --- | --- |
| Repo Owner | `pass with concern` | Source and embedded NCR workflow are checkpointed in flat `src/`; future broad changes still require one-writer discipline. |
| AI Rules Auditor | `pass` | Four-tool gateway files and SQE DailyWork automation surfaces remain in the source surface. |
| Windows Local Developer | `pass with concern` | Full Windows paths remain preferred; local runtime and generated folders stay ignored. |
| Automation Operator | `pass with concern` | Automation can rely on a reviewed source baseline after verification, but generated/runtime folders remain excluded. |
| Security / Data Reviewer | `pass with concern` | Runtime data is ignored; data-mutating scripts remain source-reviewed but must not be run blindly. |
| Release Gate Reviewer | `pass with concern` | Source layout is checkpointable after `scripts\verify.ps1` passes. |

## Residual Risk

- `audit-inference`: Parallel writing remains unsafe during any future broad restructure or data-contract change.
- `audit-inference`: Runtime/generated state remains outside the baseline and must not be staged blindly.
- `not verified`: Manual Claude/Cursor/Antigravity UI rule panels were not opened in this pass.

## Next Action

Keep source packages under `src/`, with `PYTHONPATH`/entrypoints resolving
`src` first. Verify that root `data\sqe_v2.db` remains the active database and
that the former child project directory, `src\data\sqe_v2.db`, and
`src\ncr\data\defect.db` do not exist.
