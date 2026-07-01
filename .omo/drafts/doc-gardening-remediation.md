---
slug: doc-gardening-remediation
status: awaiting-approval
intent: clear
pending-action: write .omo/plans/doc-gardening-remediation.md
approach: Apply two text-only date/count updates to markdown files identified by doc-gardening report
---

# Draft: doc-gardening-remediation

## Components (topology ledger)
| id | outcome | status | evidence path |
|----|---------|--------|---------------|
| A | Update source-baseline-manifest.md: tracked file count 180→276, date 2026-06-06→2026-06-26 | active | doc-gardening report finding #2 |
| B | Update ai-rules-compatibility.md: "Last verified" date 2026-05-25→2026-06-26 | active | doc-gardening report finding #3 |

## Open assumptions (announced defaults)
| assumption | adopted default | rationale | reversible? |
|-----------|----------------|-----------|-------------|
| Tracked file count 276 is correct | Use `git ls-files` output at time of check | Most accurate snapshot | Yes, can re-count |
| No other fields need updating in these files | Only the identified stale fields | Report-only scope: only flagged items | Yes, user can add |

## Findings (cited - path:lines)
1. `docs/harness/source-baseline-manifest.md:3` — date shows 2026-06-06, today is 2026-06-26; `:29` — track count shows 180, actual is 276
2. `docs/harness/ai-rules-compatibility.md:3` — date shows 2026-05-25, today is 2026-06-26

## Decisions (with rationale)
- In-place edits only (no restructuring, no new files): minimal change, verified by harness_check
- Both updates in same commit under same type: closely related doc maintenance

## Scope IN
- `docs/harness/source-baseline-manifest.md`: update date on line 3, tracked file count on line 29
- `docs/harness/ai-rules-compatibility.md`: update date on line 3

## Scope OUT (Must NOT have)
- No changes to AGENTS.md, README.md, CLAUDE.md, or any product code
- No business logic changes
- No file moves (production-readiness-plan.md already moved by planner)

## Open questions
None — both changes are mechanical text updates confirmed by `git ls-files`.

## Approval gate
status: awaiting-approval
<!-- When exploration is exhausted and unknowns are answered, set status: awaiting-approval. -->
<!-- That durable record is the loop guard: on a later turn read it and resume at the gate instead of re-running exploration. -->
