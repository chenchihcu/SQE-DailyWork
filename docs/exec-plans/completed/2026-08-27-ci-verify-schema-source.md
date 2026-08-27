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
- GitHub Actions Full/Coverage on `3c3e530` failed after hang watchdog dump:
  `test_create_page_updates_sidebar_active_state` blocked in
  `_ensure_has_active_suppliers` → `QMessageBox.warning` on schema-only empty
  suppliers. Follow-up skips that modal when `is_automated_runtime()` is true.
