# Source Baseline Manifest - SQETOOL

Last inspected: 2026-05-25

## Purpose

This manifest is the local source-control baseline register for AI-agent handoff. It does not stage, commit, delete, or approve files. It records the current Git boundary and the baseline risks that must be resolved before parallel AI writers or worktree automation are enabled.

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
| Repository path | `local-observed` | `C:\Users\user\Documents\SQETOOL` |
| Git root | `local-observed` | `C:/Users/user/Documents/SQETOOL` |
| Tracked files | `local-observed` | `0` |
| Modified tracked files | `local-observed` | `0` |
| Untracked files before this manifest was added | `local-observed` | `124` |
| Ignored-only entries observed | `local-observed` | `20` |
| `source_baseline_status` | `audit-inference` | `not-ready: repository has no committed source baseline` |
| Current writer mode | `audit-inference` | `single writer per worktree` |

## Tracked / Untracked / Ignored Summary

| Group | Type | Observed examples | Baseline meaning |
| --- | --- | --- | --- |
| Tracked source | `local-observed` | none | No reliable rollback or diff baseline exists yet. |
| Untracked governance | `local-observed` | `AGENTS.md`, `CLAUDE.md`, `.agents/rules/agents_gateway.md`, `.cursor/rules/agents_gateway.mdc`, `.codex/rules/project.rules`, `.claude/settings.json`, `.claude/hooks/`, `docs/harness/ai-rules-compatibility.md` | Candidate for reviewed baseline tracking. |
| Untracked product source | `local-observed` | `main.py`, `database/`, `services/`, `ui/`, `tests/`, `scripts/` | Appears to be core project source, but requires reviewed staging. |
| Ignored runtime/generated | `local-observed` | `data/`, `Outputs/`, `scratch/`, `build/`, `dist/`, caches, `import_err.txt` | Must not be captured by blind staging. |
| Local-only tool state | `local-observed` | `.claude/settings.local.json`, `.claude/worktrees/` | Keep local-only; do not use as shared policy. |

## File Classification

| List | Type | Items |
| --- | --- | --- |
| `recommended-track-list` | `audit-inference` | `AGENTS.md`, `CLAUDE.md`, `.gitignore`, `.editorconfig`, `pytest.ini`, `requirements.txt`, `README.md`, `main.py`, `run_app.bat`, `run_mig.py`, `database/**/*.py`, `services/**/*.py`, `services/assets/*.png`, `ui/**/*.py`, `tests/**/*.py`, `scripts/*.py`, `scripts/*.ps1`, `docs/**/*.md`, `.agents/rules/**`, `.cursor/rules/**`, `.codex/rules/**`, `.claude/settings.json`, `.claude/hooks/**`, `.claude/skills/**`, `.claude/agents/**` |
| `recommended-ignore-list` | `audit-inference` | `.env`, `.venv/`, `.uv-cache/`, `.uv-python/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `data/`, `Outputs/`, `scratch/`, `build/`, `dist/`, `*.log`, `*.tmp`, `import_err.txt`, `.claude/settings.local.json`, `.claude/worktrees/` |
| `needs-user-decision-list` | `audit-inference` | Data-mutating scripts before baseline approval: `run_mig.py`, `scripts/migrate_to_v2.py`, `scripts/recode_anomaly_no_all_dbs.py`; any future generated report or local DB outside ignore coverage |
| `do-not-track-list` | `audit-inference` | Runtime DBs, generated outputs, build/dist artifacts, caches, scratch folders, import error captures, local-only Claude settings, worktree folders |

## Suspicious Items

| Item | Type | Finding | Action |
| --- | --- | --- | --- |
| No committed baseline | `local-observed` | The repo has a Git root, but `git ls-files` returns no tracked files. | Do not run parallel writers. Prepare a reviewed baseline commit in a later explicit step. |
| Scratch/generated state | `local-observed` | `scratch/` is ignored as generated local state; the latest status scan did not require tracking it. | Keep `scratch/` ignored; do not delete without explicit approval. |
| Data-mutating scripts | `audit-inference` | Migration/recode scripts are source, but execution can mutate local data. | Track only after source review; command execution remains prompt/forbid by rules. |

## Baseline Commit Readiness

| Gate | Type | Status |
| --- | --- | --- |
| Git root exists | `local-observed` | `pass` |
| Governance files are visible to Git | `local-observed` | `pass` |
| Generated/runtime files are ignored | `local-observed` | `pass with residual risk` |
| Reviewed source baseline exists | `local-observed` | `blocker` |
| Scratch/generated state excluded | `local-observed` | `pass with residual risk` |
| Worktree automation readiness | `audit-inference` | `blocker until reviewed baseline commit exists` |

## Role Review Simulation

| Role | Result | Basis |
| --- | --- | --- |
| Repo Owner | `concern` | Source appears complete but untracked; baseline review is still required. |
| AI Rules Auditor | `pass` | Four-tool gateway files and SQETOOL Claude automation surfaces exist. |
| Windows Local Developer | `pass with concern` | Full Windows paths remain preferred; scratch/generated state stays ignored. |
| Automation Operator | `concern` | Automation must remain local/report-only until a baseline commit exists. |
| Security / Data Reviewer | `pass with concern` | Runtime data is ignored; migration/recode scripts need command-level controls. |
| Release Gate Reviewer | `blocker` | No reviewed source baseline commit exists. |

## Residual Risk

- `audit-inference`: Multi-AI parallel writing remains unsafe because the source baseline is absent.
- `audit-inference`: Scratch/generated state remains outside the baseline and must not be staged blindly.
- `not verified`: Manual Claude/Cursor/Antigravity UI rule panels were not opened in this pass.

## Next Action

Keep `SQETOOL` in single-writer mode. Next approved phase should review data-mutating scripts and scratch warnings, run `git add --dry-run -- <approved paths>`, then create a reviewed source baseline commit only after user approval.
