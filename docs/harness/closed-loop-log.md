# Closed-loop Log

Use this file for reusable lessons from debugging, regressions, repeated failures, or Investigation Path work.

## Entry Template

```text
Date:
Task:
Changes:
Impact:
Verification:
Residual risk:
Next action:
Debug/RCA (when applicable):
Observed:
Root cause:
Fix:
Harness update needed:
Destination:
```

## Initial Entry

Date: 2026-05-16
Task: Install closed-loop harness.
Changes: Added root `AGENTS.md`, repo harness docs, exec-plan directories, a harness structure check, and a full verification entrypoint.
Impact: SQETOOL now has a single repo-local knowledge map while preserving tool-specific gateway files as adapters.
Verification: Run `scripts\harness_check.ps1` and `scripts\verify.ps1`.
Residual risk: full verification may still expose unrelated existing test/runtime debt; do not weaken the gate.
Next action: Use weekly harness gardening to report drift, then remediate only when explicitly requested.
Debug/RCA (when applicable):
Observed: The repo already had project command rules, tests, and smoke helpers, but no root `AGENTS.md` or canonical verification script.
Root cause: Repo-local guidance and verification existed in separate places without a single agent knowledge map.
Fix: Add repo `AGENTS.md`, harness docs, exec-plan directories, a harness structure check, and a full verification script.
Harness update needed: yes
Destination: `AGENTS.md`, `docs/harness/`, `docs/exec-plans/`, `scripts/harness_check.ps1`, `scripts/verify.ps1`, `.codex/rules/project.rules`

## Qt Visual Evidence Entry

Date: 2026-05-18
Task: Stop repeated false UI findings from Qt offscreen CJK rendering.
Changes: Added a native Qt visual probe and documented that offscreen Qt is structural-only evidence.
Impact: Future homepage and desktop UI reviews must use native Windows Qt screenshots before judging Chinese text rendering or typography.
Verification: Run `scripts\qt_visual_probe.py`; run `scripts\harness_check.ps1`.
Residual risk: native visual capture still depends on the local Windows desktop and installed fonts.
Next action: Use offscreen only for startup/widget smoke checks; use native capture for visual review.
Debug/RCA (when applicable):
Observed: Offscreen screenshots rendered Chinese text as square glyphs even though the Windows Qt platform displayed the same UI correctly.
Root cause: Qt offscreen on this host does not reliably load the Windows CJK font set used by the app.
Fix: Add `scripts/qt_visual_probe.py`, update repo guidance, and make the harness check require the native visual evidence rule.
Harness update needed: yes
Destination: `AGENTS.md`, `docs/harness/README.md`, `docs/harness/closed-loop-log.md`, `scripts/qt_visual_probe.py`, `scripts/harness_check.ps1`, `.codex/rules/project.rules`
