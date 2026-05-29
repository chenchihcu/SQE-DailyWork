# Harness Quality Score

This scorecard tracks whether the repository is legible and verifiable for future Codex runs.

| Area | Current | Evidence | Next action |
| --- | --- | --- | --- |
| Knowledge map | Pass | `AGENTS.md` points to README, Cursor and Antigravity gateways, risk ledger, harness docs, exec plans, verify gate, and command rules. | Keep links current when docs move. |
| Verification gate | Pass | `scripts/verify.ps1` runs compileall, unittest discovery, offscreen UI smoke, and harness structure check. | Add focused checks only for recurring failures. |
| Command policy | Pass | `.codex/rules/project.rules` keeps safe checks allowed and migration/apply operations reviewed. | Add rules only for repeated safe commands. |
| Closed-loop learning | Watch | `docs/harness/closed-loop-log.md` exists; entries must be added after real debugging lessons. | Review during doc gardening. |
| Documentation freshness | Watch | Active docs are intentionally small; automation is report-first. | Promote repeated drift into checks or source docs. |

## Grading Rules

- `Pass`: current and backed by an executable check or clear source.
- `Watch`: current enough to use, but needs recurring review.
- `Fail`: stale, missing, or contradicted by code/config.

Do not lower the global Hard Trigger floor to improve this score.
