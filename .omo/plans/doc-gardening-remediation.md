# doc-gardening-remediation - Work Plan

## TL;DR (For humans)

**What you'll get:** Doc gardening 發現的兩筆過期資訊修復：`source-baseline-manifest.md` 的檔案計數與日期更新，以及 `ai-rules-compatibility.md` 的驗證日期更新。

**Why this approach:** 這兩項都是純文字更新，沒有架構或邏輯變更，直接編輯最有效率。

**What it will NOT do:** 不會動到產品程式碼、AGENTS.md、README.md 或其他核心文件。

**Effort:** Quick
**Risk:** Low - 純文字修改，無副作用
**Decisions to sanity-check:** 無

Your next move: 審閱後 approve 即可執行。

---

> TL;DR (machine): Quick | Low | Two date/count updates in harness docs

## Scope
### Must have
- `docs/harness/source-baseline-manifest.md`: tracked file count 180→276, date 2026-06-06→2026-06-26
- `docs/harness/ai-rules-compatibility.md`: "Last verified" date 2026-05-25→2026-06-26

### Must NOT have (guardrails, anti-slop, scope boundaries)
- No product code changes
- No file moves beyond what planner already did
- No changes to AGENTS.md, README.md, CLAUDE.md

## Verification strategy
- Test decision: none (text-only edits, no testable logic)
- Evidence: `scripts/harness_check.ps1` passes after changes
- Verification: `git diff` and `harness_check.ps1`

## Execution strategy
### Parallel execution waves
Single wave: 2 independent tasks

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1. Update source-baseline-manifest.md | none | none | Todo 2 |
| 2. Update ai-rules-compatibility.md | none | none | Todo 1 |

## Todos
<!-- APPEND TASK BATCHES BELOW THIS LINE WITH edit/apply_patch - never rewrite the headers above. -->
- [ ] 1. Update `source-baseline-manifest.md` date and count
  What to do / Must NOT do: Line 3: `2026-06-06` → `2026-06-26`. Line 29: `180` → `276`. Do not modify any other line or field.
  Parallelization: Wave 1 | Blocked by: none | Blocks: none
  References: `docs/harness/source-baseline-manifest.md:3,29`
  Acceptance criteria: `Select-String -Path docs/harness/source-baseline-manifest.md -Pattern '276|2026-06-26'` returns matches; no other modifications
  QA scenarios: `git diff docs/harness/source-baseline-manifest.md` shows exactly 2 changes
  Commit: Y | `docs(harness): update source-baseline-manifest.md date and tracked file count`

- [ ] 2. Update `ai-rules-compatibility.md` date
  What to do / Must NOT do: Line 3: `2026-05-25` → `2026-06-26`. Do not modify any other line or field.
  Parallelization: Wave 1 | Blocked by: none | Blocks: none
  References: `docs/harness/ai-rules-compatibility.md:3`
  Acceptance criteria: `Select-String -Path docs/harness/ai-rules-compatibility.md -Pattern '2026-06-26'` returns match at line 3
  QA scenarios: `git diff docs/harness/ai-rules-compatibility.md` shows exactly 1 change
  Commit: Y (bundled with todo 1 in same commit)

## Final verification wave
- [ ] F1. Plan compliance audit — only the 2 specified files changed, exact fields
- [ ] F2. Code quality review — N/A (text-only)
- [ ] F3. Real manual QA — `git diff` + `harness_check.ps1` passes
- [ ] F4. Scope fidelity — no product code touched

## Commit strategy
Single commit: `docs(harness): update source-baseline-manifest and ai-rules-compatibility dates`

## Success criteria
- `docs/harness/source-baseline-manifest.md:3` shows `2026-06-26`
- `docs/harness/source-baseline-manifest.md:29` shows `276`
- `docs/harness/ai-rules-compatibility.md:3` shows `2026-06-26`
- `scripts/harness_check.ps1` passes
