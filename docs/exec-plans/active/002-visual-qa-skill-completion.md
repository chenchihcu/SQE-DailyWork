# 002#SQE DailyWork 視覺驗收技能完整化

Plan status: active

## Goal

把 `sqe-dailywork-visual-qa` 從分散的 probe、button audit 與 regression 操作手冊，提升為可重複、可稽核、fail-closed 的 AppearanceSettings 驗收 profile；保留 SQLite、偏好 payload、產品 UI 與既有 visual baseline 的獨立 promotion gate。

## Decisions

- Repo-local `.agents\skills\sqe-dailywork-visual-qa` 是 project-specific SSOT；`.claude\skills\sqe-dailywork-visual-qa` 必須逐檔 mirror。
- 沿用 `scripts\verify.ps1`，新增 `-Profile AppearanceSettings`，不建立平行全域 harness。
- Behavior、crash safety、visual correctness 是三個不可互相替代的 gate。
- Required baseline 一律走 candidate → human review → reviewed promotion；不盲目覆寫。
- 所有 native visual evidence 使用 Windows Qt；offscreen 僅作 structural smoke。
- 全域 trigger linter 修改另列授權 gate，不在本 repo 內修改全域治理資產。

## Progress

- [ ] Phase 0 backup and current-state hashes
- [ ] Phase 1 route keywords JSON parse/schema/smoke gate
- [ ] Phase 2 skill version, reference split, route terminology, mirror sync
- [ ] Phase 3 `AppearanceSettings` verification profile
- [ ] Phase 4 focus, geometry, top-level dialog, overflow, contrast assertions
- [ ] Phase 5 renderer and fixture provenance
- [ ] Phase 6 baseline candidate and reviewed promotion
- [ ] Phase 7 docs, harness, command policy, closed-loop synchronization
- [ ] Phase 8 focused/native/full verification
- [ ] Phase 9 global trigger-linter namespace change (separate authorization)

## Verification

Required final evidence:

- focused behavior unittest bundle pass
- button audit exit `0`, no FAILED/Worker/SEH/Exceptions residual
- native `appearance-settings` probe pass at 1.0/1.25/1.5 and 1024×680
- pixel regression pass at all required scales, or explicit candidate/reviewed outcome
- `scripts\harness_check.ps1` pass
- summary distinguishes `verified`, `not verified`, `not pass`, and `blocked`

## Remaining work

Do not promote a visual baseline or modify the global trigger linter until the relevant independent approval gate is satisfied. Move this plan to `docs\exec-plans\completed\` only after all repo-local gates are green and the final report records any external blocker.
