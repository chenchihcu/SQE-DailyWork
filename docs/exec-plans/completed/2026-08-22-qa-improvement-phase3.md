# QA Improvement — Phase 3

Plan status: completed

## Goal

Close Phase 3 QA gaps: coverage gate, portable install QA, soak/stability smoke,
installer QA spec + Inno POC. Authenticode signing deferred to Phase 4.

## Waves

| Wave | Item | Status |
|------|------|--------|
| 3.1 | `.coveragerc` + verify `-Profile Coverage` | closed |
| 3.2 | `portable_install_smoke.ps1` + checklist | closed |
| 3.3 | `test_stability_smoke.py` + verify `-Profile Soak` | closed |
| 3.4 | Installer spec + Inno POC | closed |
| 3.5 | Coverage baseline fail-under | closed |
| 4.x | Authenticode + signed installer | deferred |

## Verification

- `scripts/verify.ps1 -Profile Soak` — PASS
- `scripts/verify.ps1 -Profile Coverage` — tests PASS; baseline gate ~81% line (`docs/release/coverage-baseline.json`)
- `scripts/portable_install_smoke.ps1 -UseExistingDist` — PASS (zip includes `build-info.json`)
- `scripts/build_windows.ps1` — PASS after build-info order + PYTHONPATH fix
- `scripts/harness_check.ps1` — PASS (membership `625`)

## Residual

- Phase 4 Authenticode (`docs/release/phase4-signing-deferred.md`)
- Unsigned Inno `setup.exe` is experimental only
- 8h manual soak remains checklist-only
