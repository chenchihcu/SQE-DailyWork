# Harness Quality Score

This scorecard tracks whether the repository is legible and verifiable for future Codex runs.

| Area | Current | Evidence | Next action |
| --- | --- | --- | --- |
| Knowledge map | Pass | `AGENTS.md` points to README, Cursor and Antigravity gateways, risk ledger, harness docs, exec plans, verify gate, and command rules. | Keep links current when docs move. |
| Verification gate | Pass | `scripts/verify.ps1` isolates a verified DB snapshot, supports Focused/Full, and runs compileall, unittest, offscreen smoke, native three-DPI belt, visual regress, and harness. | Keep focused patterns tied to recurring RCA tests. |
| Command policy | Pass | `.codex/rules/project.rules` keeps safe checks allowed and migration/apply operations reviewed. | Add rules only for repeated safe commands. |
| Closed-loop learning | Watch | `docs/harness/closed-loop-log.md` exists; entries must be added after real debugging lessons. | Review during doc gardening. |
| Documentation freshness | Pass | Live release membership, active-plan lifecycle, do-not-track state, and visual target/baseline mapping are executable harness checks. | Update source docs and manifest in the same change as contract drift. |

## Grading Rules

- `Pass`: current and backed by an executable check or clear source.
- `Watch`: current enough to use, but needs recurring review.
- `Fail`: stale, missing, or contradicted by code/config.

Do not lower the global Hard Trigger floor to improve this score.
