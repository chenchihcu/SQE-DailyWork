# 001#全面缺陷修復與發布驗證

Plan status: completed

Completed: 2026-09-02

## Goal

Preserve the current dirty release candidate, fix every reproduced source/release
gate failure and actionable warning, and produce evidence for Full, Coverage, Soak,
and a fresh Release build. Stop at the human commit checkpoint; do not commit,
push, publish, promote schema, or write the formal database.

## RCA

- Three Full failures are stale tests: the manager queue must retain
  `source_page_key=PAGE_MANAGER_VIEW`, and both statistics pages now mount their
  flat command rows inside a visible `AnalyticsWorkflowShell`.
- Resource warnings come from unclosed test-owned in-memory SQLite connections
  and one workbook. The deprecation warning comes from a test directly calling
  the intentionally deprecated NCR stylesheet compatibility shim.
- Frozen startup fails with WinError 127 because PyInstaller resolves
  `icuuc.dll` from the host Codex/Poppler PATH. That DLL exports ICU 78-suffixed
  symbols while `Qt6Core.dll` imports Windows' unversioned ICU symbols.
- Broad `collect_all("PySide6")` and package-wide `collect_submodules()` pull
  unused Qt plugins and `ncr.tests` into the artifact, creating avoidable DLL and
  optional-module warnings.
- The release scripts have no frozen-smoke timeout, overwrite `dist/` before the
  candidate passes, mutate tracked `src/build_info.py`, and can leave a stale
  successful `release-gate-summary.json` after a later failed run.

## Locked implementation

- Update stale assertions and close test-owned resources; do not revert the
  current production UI/navigation behavior.
- Use PyInstaller's normal hooks and source-discovered imports, exclude tests and
  unused plotting modules, sanitize the packaging PATH, and fail on foreign
  Codex-runtime DLL collection or unclassified release warnings.
- Generate build metadata in an untracked staging source overlay. Build and smoke
  in staging, apply a bounded 120-second timeout, then promote only a passing
  candidate while retaining the last verified artifact.
- Always replace the release summary with current-run state, including failure
  state; never leave an older PASS as current evidence.
- Preserve the formal DB and visual baselines. No baseline refresh is allowed
  without a diagnosed data/rendering cause and separate approval.

## Verification gates

- Focused unittest modules under warning-as-error plus compile/diff checks.
- `scripts\harness_check.ps1` and read-only formal promotion audit.
- Full with native Windows visual belt and formal fingerprint invariance.
- Coverage complete chain at line coverage >= 71.0%.
- Soak 10 cycles.
- Fresh Release and `-UseExistingDist`, current summary, matching SHA256,
  warning audit, frozen/portable smoke marker, and no timeout/foreign ICU DLL.

## Stop condition

After all technical gates pass, report the complete candidate diff and stop for
the user's separate commit authorization. Only a post-commit clean-candidate
rerun can support a final `release-ready` claim.

## Completion evidence

- Full: `scratch/verify-full-log-final.txt` — exit 0
- Coverage: `scratch/verify-coverage-final.log` — exit 0, line coverage ≥ 71%
- Soak: `scratch/verify-soak-final.log` — exit 0, 10 cycles
- Release: `scratch/verify-release-final.log` — exit 0; summary `scratch/release-gate-summary.json` `passed: true`
- Release zip SHA-256: `52A181749C869F0160743D88A2A7D0A3B241F958E93A8DFD6AE22D8769381F9A`
- Verified archive: `Outputs/release-archive/20260902T122524Z-6abb689/`
- Human commit checkpoint: pending (dirty tree ~318 files)
