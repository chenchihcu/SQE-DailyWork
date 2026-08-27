# CI Verify Schema-Only Source — 2026-08-27

Plan status: completed

## Goal

Let GitHub Actions and other clean clones run `scripts/verify.ps1` without
gitignored `data/sqe_v2.db`. Keep the formal database unwritten. Do not treat
CI native visual as evidence.

## Decisions

- Schema-only source uses `create_schema` on a scratch file beside the
  disposable destination, then the existing WAL-safe online backup.
- Do not call `initialize_database()` for the CI source (avoids legacy/NCR
  migration scans).
- Local verify without `-AllowSchemaOnlySource` still fails if the source DB is
  missing.
- CI Full skips native visual belt and pixel baselines (`-SkipNativeVisual` /
  `GITHUB_ACTIONS` / schema-only mode). Offscreen smoke still runs.
- Cloud Agent git uses `cursor/ci-verify-schema-source-7802` + PR; conflict with
  repo TBD is recorded in `docs/harness/contradiction-log.md`.

## Progress

- `src/database/verify_prepare.py` + `scripts/prepare_verify_database.py`
- `scripts/verify.ps1` flags and Focused pattern `test_prepare_verify_database.py`
- `.github/workflows/verify.yml` passes the flags on Full / Coverage / Soak
- Harness docs, AGENTS/CLAUDE, Codex verify match examples

## Verification

- Linux: `python -m unittest tests.test_prepare_verify_database tests.test_database_isolation tests.test_database_backup tests.test_app_paths`
- GitHub Actions Verify on the PR branch (Windows) is the remaining gate

## Remaining work

- Native visual belt and Windows packaging stay local-only (`not verified` here)
- First live `data/sqe_v2.db` `initialize_database()` still needs explicit user
  authorization
- GitHub Actions Full/Coverage on `33b9797` cancelled at 120 minutes after
  `test_partial_statistics_failure_is_not_rendered_as_empty_data` (Soak succeeded).
  A cancelled job is not green. Follow-up adds per-test hang abort + unittest `-v`.
