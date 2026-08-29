# SQE DailyWork Production Release 缺口稽核報告

**稽核日期：** 2026-08-29  
**稽核範圍：** validate-production-release 四支柱（Artifact / Environment / Smoke / Rollback）  
**工作區 commit：** `723e6fe`（Align tests and harness docs with BulletListWidget numbered payloads）  
**稽核模式：** 唯讀（未執行 promotion `-Apply`、未重跑 Full verify、未重建 dist）

---

## 執行摘要

| 問題 | 結論 |
|------|------|
| 今日能否 cut unsigned portable release？ | **否** — CI 全紅、harness_check 本地 FAIL、無近期 verify 證據鏈、dist 產物過期 |
| Formal DB promotion 狀態？ | **已全部套用** — 6 項關鍵 `migration_meta` 皆為 `1`；dry-run 皆 `ready: true` |
| CI green = production-ready？ | **否** — 差 5+ 層 gate（native visual、build、portable、workflow smoke、button audit） |
| Top 3 改善項 | ① 修復 CI 掛起 + harness gate ② 新增 Release Profile wrapper ③ 統一 promotion status 稽核腳本 |

---

## 1. Gate 盤點（支柱對照）

### 1.1 `scripts/verify.ps1` Profiles

| Profile | 步驟 | PASS 訊號 | 證據位置 |
|---------|------|-----------|----------|
| **Full** | compileall → unittest (2-chunk) + NCR + 3 pytest → offscreen smoke → native belt → pixel baseline (1.0/1.25/1.5) → harness_check | `Full verification passed.` + exit 0 | `scratch/verify-full-log-final.txt`（**本次缺失**） |
| **Focused** | compileall → 21 focused patterns → offscreen smoke → form-density + event-create probe → harness_check | `Focused verification passed.` | 無近期 log |
| **Coverage** | compileall → 4-chunk coverage + NCR + pytest → coverage xml/html → `assert_coverage_baseline.py` → harness_check | `Coverage verification passed.` | `scratch/verify-coverage-*-final*.log`（**本次缺失**） |
| **Soak** | `tests.test_stability_smoke`（預設 10 cycles）→ harness_check | `Soak verification passed.` | `scratch/verify-soak-final.log`（**本次缺失**） |

**共用前置：** disposable DB（`prepare_verify_database.py`）+ `case_actions_v1` preflight + formal DB fingerprint 前後比對。

### 1.2 CI（`.github/workflows/verify.yml`）

| Job | 命令 | 限制 |
|-----|------|------|
| verify-full | `-Profile Full -AllowSchemaOnlySource -SkipNativeVisual` | 無 formal DB、無 native visual |
| verify-coverage | `-Profile Coverage -AllowSchemaOnlySource` | 無 formal DB |
| verify-soak | `-Profile Soak -AllowSchemaOnlySource` | 無 formal DB |

**最新 CI run：** [#33223294095](https://github.com/chenchihcu/SQE-DailyWork/actions/runs/33223294095) — **全部 FAIL**（2026-08-29）

| Job | 失敗原因 |
|-----|----------|
| verify-full | `unittest chunk 1 failed with exit code 3` — hang watchdog：`test_analysis_tab_exposes_hypothesis_actions` 超過 180s |
| verify-coverage | 同上（chunk 1 hang） |
| verify-soak | `harness_check failed` — membership drift：manifest 預期 682、實際 690（**已於本地 manifest 更新為 690，CI 當時落後**） |

### 1.3 打包與 Portable Smoke

| Gate | 命令 | PASS 條件 |
|------|------|-----------|
| Windows build | `scripts/build_windows.ps1` | exe + zip + `build-info.json`；frozen `--smoke-exit`（`Start-Process -Wait` + `logs/smoke_exit.ok`） |
| Portable smoke | `scripts/portable_install_smoke.ps1 -UseExistingDist` | zip 解壓後 frozen smoke 三項檢查 |

**現有 dist 狀態（過期）：**

| 欄位 | 值 |
|------|-----|
| `build-info.json` version | 1.2.0 |
| git_commit | `8a02f7d`（**落後 HEAD `723e6fe`**） |
| build_timestamp | 2026-08-28T03:51:05Z |
| dirty_worktree | true |
| zip SHA256 | `FB3FEA29494590ACB555579DCA78001888EB5E07F6D81F50738524F7674A9460` |

### 1.4 未納入 verify 主線的 Smoke

| Gate | 命令 | 狀態 |
|------|------|------|
| Workflow API smoke | `scripts/smoke_test_v2.py` | 無近期執行證據 |
| Button audit | `scripts/button_audit_report.py` | 無 `button_audit_report.md` 產物 |

---

## 2. Formal DB Promotion 狀態（唯讀盤點）

**Formal DB fingerprint：** `8d2b70d5fd188ca893475ca496d2105a99e38f0cc21afe54d6c9745ca064405a`  
**詳細 JSON：** [`scratch/formal-db-promotion-status.json`](../../scratch/formal-db-promotion-status.json)

| Promotion | migration_meta | Dry-run | 資料列 | 狀態 |
|-----------|----------------|---------|--------|------|
| case_actions_v1 | `1` | canonical 14 actions | case_actions: 14 | **已套用** |
| anomaly_attachments_contract_v1 | `1` | audit OK | attachments: 0 | **已套用**（無附件資料） |
| anomaly_hypotheses_v1 | `1` | audit OK | hypotheses: 0 | **已套用**（無假設資料） |
| anomaly_repeat_links_v1 | `1` | ready, 22 links | repeat_links: 22 | **已套用** |
| product_records_view_is_active_v1 | `1` | ready, counts aligned | VIEW + is_active filter | **已套用** |
| defect_supplier_id_backfill_v1 | `1` | — | — | **已套用** |

**結論：** 無待套用 promotion；本次稽核**不需要** `-Apply`。若未來有新 migration，須依標準作業（備份 → dry-run → 使用者明示「繼續」→ Apply → post-verify）。

**Audit JSON 產物：**

- `scratch/phase2r-attachment-audit-gap.json`
- `scratch/phase3-hypothesis-audit-gap.json`
- `scratch/product-records-view-audit-gap.json`

---

## 3. 缺口矩陣（P0–P3）

### 支柱 1：Artifact Verification

| ID | 缺口 | 等級 | 現況 |
|----|------|------|------|
| A1 | CI 不建置 exe/zip | P1 | 需本地 `build_windows.ps1` |
| A2 | portable smoke 未納入 verify | P1 | 手動 checklist only |
| A3 | dist 產物過期（commit 落後） | P0 | 不可直接發布現有 zip |
| A4 | 無 zip SHA256 發布紀錄欄位 | P2 | build-info 不含 hash |
| A5 | Authenticode 簽章延後 | P1 | accepted risk（Phase 4） |
| A6 | 無 SAST/CVE gate | P3 | 未實作 |

### 支柱 2：Environment Parity

| ID | 缺口 | 等級 | 現況 |
|----|------|------|------|
| E1 | CI schema-only ≠ formal DB | P1 | 設計如此；release 需本地 disposable from formal |
| E2 | Python 3.12 (CI) vs 3.14.3 (本地) | P2 | 版本漂移風險 |
| E3 | 無統一 promotion status dashboard | P2 | 本次以 `scratch/audit_formal_db_status.py` 暫補 |
| E4 | Formal DB promotions | — | **全部已套用** |

### 支柱 3：Smoke & Sanity Testing

| ID | 缺口 | 等級 | 現況 |
|----|------|------|------|
| S1 | CI ≠ local release gate | **P0** | CI 跳過 native visual |
| S2 | CI 全紅（hang + harness） | **P0** | run #33223294095 |
| S3 | harness_check 本地 FAIL | **P0** | AGENTS.md 32816 bytes > 32768 budget |
| S4 | 無 scratch verify 證據鏈 | P1 | Full/Coverage/Soak log 皆缺失 |
| S5 | smoke_test_v2 游離 | P1 | 未納入 verify |
| S6 | button audit 游離 | P1 | AGENTS dual gate 未自動化 |
| S7 | 8h soak 未自動化 | P3 | 10-cycle only |

### 支柱 4：Rollback Preparedness

| ID | 缺口 | 等級 | 現況 |
|----|------|------|------|
| R1 | 無統一 rollback runbook | P2 | 分散於 risk-ledger / promotion 腳本 |
| R2 | 備份可還原性無自動 gate | P2 | `backup_data.ps1` 存在但未驗證 integrity |
| R3 | 無 artifact registry | P3 | 僅保留 dist/ 目錄 |
| R4 | Schema rollback 禁止 partial SQL | — | **正確** |

---

## 4. 證據盤點（Evidence Inventory）

| 證據類型 | 預期路徑 | 本次狀態 |
|----------|----------|----------|
| Local Full verify log | `scratch/verify-full-log-final.txt` | **缺失** |
| Local Coverage log | `scratch/verify-coverage-*-final*.log` | **缺失** |
| Coverage summary | `scratch/coverage-summary.json` | **缺失** |
| Local Soak log | `scratch/verify-soak-final.log` | **缺失** |
| CI Full PASS | GitHub Actions verify-full | **FAIL** (#33223294095) |
| CI Coverage PASS | GitHub Actions verify-coverage | **FAIL** |
| CI Soak PASS | GitHub Actions verify-soak | **FAIL** |
| Frozen build-info | `dist/SQE_DailyWork/build-info.json` | **存在但過期** |
| Portable zip SHA256 | 見上表 | 已記錄 |
| Button audit report | `button_audit_report.md` | **缺失** |
| Formal DB audit JSON | `scratch/*-audit-gap.json` | **本次產出** |
| harness_check | 本地執行 | **FAIL**（AGENTS.md size） |

**上次已知 PASS 證據（歷史，非本次重驗）：** Phase 8 exec-plan 引用 `scratch/verify-full-chunked-final.log`、`scratch/verify-soak-final.log`（檔案已不在工作區）。

---

## 5. 風險登錄殘餘項

| 風險 | 狀態 | 發布影響 |
|------|------|----------|
| Product ownership VERIFY CSV | Active | 需人工分類 |
| Phase 0 raw hash drift | Accepted | 不阻擋 release |
| Visit display 不一致 | Active | UAT 建議 |
| 未簽章 binary | Phase 4 deferred | SmartScreen 預期 |
| Coverage profile log 證據 | residual open | 須重跑 Windows 4-chunk |

---

## 6. 改善建議 Backlog

| 優先 | 項目 | Effort | 風險降低 |
|------|------|--------|----------|
| **P0** | 修復 `test_analysis_tab_exposes_hypothesis_actions` CI 180s hang | M | CI 恢復綠燈 |
| **P0** | 縮減 AGENTS.md 至 ≤32768 bytes 或調整 harness budget | S | harness_check PASS |
| **P0** | 文件化「CI green ≠ release ready」於 runbook | S | 誤判風險 |
| **P1** | 新增 `verify.ps1 -Profile Release`（build + portable + smoke_test_v2 + button audit） | M | 單一 release gate |
| **P1** | 新增 `scripts/audit_formal_db_promotion_status.ps1`（正式版，取代 scratch 暫用腳本） | S | promotion 可視化 |
| **P1** | build-info 加入 zip SHA256 | S | 產物追溯 |
| **P2** | 合併 rollback decision tree 至 runbook | S | 回滾可執行性 |
| **P2** | CI Python 版本對齊本地 3.14 或矩陣測試 | M | parity |
| **P3** | Phase 4 Authenticode 簽章 | L | 企業部署 |
| **P3** | 依賴 CVE 掃描納入 gate | M | 安全 |

---

## 7. 成功準則回答

1. **今日 cut release？** 不可。缺 CI PASS、本地 harness PASS、verify 證據鏈、新 build。
2. **Formal DB promotion？** 全部已套用，無待執行 migration。
3. **CI vs production-ready 差距？** 至少 5 層：native visual、Full local verify、build、portable smoke、workflow/button smoke。
4. **Top 3 改善？** 修 CI hang → 修 harness AGENTS size → Release Profile wrapper。

---

## Changes

- 新增本稽核報告與 formal DB 狀態 JSON
- 新增 `scratch/audit_formal_db_status.py`（暫用盤點腳本）
- 新增 `docs/release/production-release-runbook.md`

## Impact

- 明確判定：**目前不可 production cut**
- Formal DB：**無需額外 promotion**

## Verification

- 唯讀盤點：formal DB fingerprint、migration_meta、5 套 audit dry-run
- CI：`gh run view 33223294095`
- 本地：`harness_check.ps1`（FAIL：AGENTS.md size）

## Residual risk

- 未重跑 Full verify / build / portable smoke（耗時 gate，依計畫刻意跳過）
- dist 產物過期需重建後才能發布

## Next action

1. 修復 P0 項目（CI hang + AGENTS.md size）使 CI 與 harness 恢復綠燈
2. 重跑本地 Full + Coverage + Soak 並留存 `scratch/*-final*.log`
3. 重建 dist 並執行 portable smoke
