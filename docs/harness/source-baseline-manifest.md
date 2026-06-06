# Source Baseline Manifest - SQETOOL

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
| Repository path | `local-observed` | `C:\Users\user\Documents\SQE DailyWork\SQETOOL` |
| Git root | `local-observed` | `C:/Users/user/Documents/SQE DailyWork/SQETOOL` |
| Tracked files after Phase 0 checkpoint | `audit-inference` | `180` |
| Modified tracked files after Phase 0 checkpoint | `audit-inference` | `0` |
| Untracked files after Phase 0 checkpoint | `audit-inference` | `0` |
| Ignored-only entries observed before Phase 0 checkpoint | `local-observed` | `29` |
| `source_baseline_status` | `audit-inference` | `ready: reviewed Phase 0 source baseline checkpoint` |
| Current writer mode | `audit-inference` | `single writer per worktree until src restructure checkpoint is complete` |

## Tracked / Untracked / Ignored Summary

| Group | Type | Observed examples | Baseline meaning |
| --- | --- | --- | --- |
| Tracked source | `audit-inference` | `main.py`, `database/`, `services/`, `ui/`, `ncr/`, `tests/`, `scripts/`, `docs/`, governance rules | Reviewed source surface for the Phase 0 checkpoint. |
| Embedded NCR source | `audit-inference` | `ncr/embed.py`, `ncr/db/`, `ncr/models/`, `ncr/services/`, `ncr/ui/`, `ncr/tests/`, `ncr/README.md` | Keep as the embedded warehouse nonconforming-product workflow. |
| Removed NCR residue | `audit-inference` | `ncr/.github/`, `ncr/.gitignore`, `ncr/.ruff.toml`, one-off logs, probe PNGs, standalone review/skill notes | Standalone project residue; not part of the embedded workflow baseline. |
| Ignored runtime/generated | `local-observed` | `data/`, `Outputs/`, `scratch/`, `build/`, `dist/`, caches, local runtimes, `import_err.txt` | Must not be captured by blind staging. |
| Local-only tool state | `local-observed` | `.claude/settings.local.json`, `.claude/worktrees/`, `.playwright-mcp/` logs | Keep local-only; do not use as shared policy. |

## File Classification

| List | Type | Items |
| --- | --- | --- |
| `recommended-track-list` | `audit-inference` | `AGENTS.md`, `CLAUDE.md`, `.gitignore`, `.editorconfig`, `pytest.ini`, `requirements.txt`, `README.md`, `main.py`, `run_app.bat`, `run_mig.py`, `database/**/*.py`, `services/**/*.py`, `services/assets/*.png`, `ui/**/*.py`, `ui/assets/**/*.svg`, `tests/**/*.py`, `scripts/*.py`, `scripts/*.ps1`, `docs/**/*.md`, `ncr/**/*.py`, `ncr/**/*.md`, `ncr/ui/assets/*.svg`, `.agents/rules/**`, `.cursor/rules/**`, `.codex/rules/**`, `.claude/settings.json`, `.claude/hooks/**`, `.claude/skills/**`, `.claude/agents/**` |
| `recommended-ignore-list` | `audit-inference` | `.env`, `.venv/`, `.uv-cache/`, `.uv-python/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `data/`, `Outputs/`, `scratch/`, `build/`, `dist/`, `*.log`, `*.tmp`, `import_err.txt`, `.claude/settings.local.json`, `.claude/worktrees/`, `.playwright-mcp/` |
| `needs-user-decision-list` | `audit-inference` | Data-mutating scripts before execution: `run_mig.py`, `scripts/migrate_to_v2.py`, `scripts/recode_anomaly_no_all_dbs.py`, `scripts/migrate_ncr_defects_to_main_db.py` |
| `do-not-track-list` | `audit-inference` | Runtime DBs, generated outputs, build/dist artifacts, caches, scratch folders, import error captures, local-only assistant settings, worktree folders |

## Suspicious Items

| Item | Type | Finding | Action |
| --- | --- | --- | --- |
| Pending `src/` restructure | `audit-inference` | Phase 0 source is checkpointable, but the flat `src/` restructure is still pending. | Keep single-writer mode and run the approved restructure plan next. |
| Scratch/generated state | `local-observed` | `scratch/`, `Outputs/`, runtime DBs, caches, and local runtimes remain ignored as generated local state. | Keep ignored; do not stage blindly. |
| Data-mutating scripts | `audit-inference` | Migration/recode scripts are source, but execution can mutate local data. | Track source after review; run only through approved verification or migration plans. |

## Baseline Commit Readiness

| Gate | Type | Status |
| --- | --- | --- |
| Git root exists | `local-observed` | `pass` |
| Governance files are visible to Git | `local-observed` | `pass` |
| Generated/runtime files are ignored | `local-observed` | `pass with residual risk` |
| Reviewed source baseline exists | `audit-inference` | `pass after Phase 0 checkpoint` |
| Scratch/generated state excluded | `local-observed` | `pass with residual risk` |
| Worktree automation readiness | `audit-inference` | `hold until src restructure checkpoint and verification complete` |

## Role Review Simulation

| Role | Result | Basis |
| --- | --- | --- |
| Repo Owner | `pass with concern` | Source and embedded NCR workflow are checkpointed, but a high-risk `src/` restructure is still pending. |
| AI Rules Auditor | `pass` | Four-tool gateway files and SQETOOL automation surfaces remain in the source surface. |
| Windows Local Developer | `pass with concern` | Full Windows paths remain preferred; local runtime and generated folders stay ignored. |
| Automation Operator | `concern` | Keep single-writer mode until the restructure checkpoint and full verification pass. |
| Security / Data Reviewer | `pass with concern` | Runtime data is ignored; data-mutating scripts remain source-reviewed but must not be run blindly. |
| Release Gate Reviewer | `hold` | Phase 0 is checkpointable; release readiness requires `scripts\verify.ps1` and root `scripts\verify_all.ps1` after restructure. |

## Residual Risk

- `audit-inference`: Parallel writing remains unsafe until the `src/` restructure checkpoint is complete and verified.
- `audit-inference`: Runtime/generated state remains outside the baseline and must not be staged blindly.
- `not verified`: Manual Claude/Cursor/Antigravity UI rule panels were not opened in this pass.

## Next Action

Complete the approved flat `src/` restructure from
`docs\exec-plans\active\src-package-restructure.md` only after Phase 0 is
checkpointed. Verify that `data\sqe_v2.db` remains the active database and that
no `src\data\sqe_v2.db` or `src\ncr\data\defect.db` is created.
