# 004#異常分析 UI 簡化（Phase 1–7）

Plan status: active

Spec status: APPROVED

## Goal

將案件工作台「異常分析」分頁由五種 modal CRUD 操作，重構為 SQE 調查工作區：同頁補充分析紀錄、直接填寫原因結論、進階比較可能原因選用；儲存後停留在異常分析分頁並保留捲動／展開狀態；Phase 6–7 補齊驗證佐證關聯提示與離開草稿完整性。

來源：[ChatGPT 分享計畫](https://chatgpt.com/share/6a9e14a0-f2f4-83e8-996c-2b757c70efd7)（implementation-ready Phase 1–7）。

## Decisions

- **不改 schema / migration / 正式 DB。** 沿用 `anomaly_analysis_notes`、`anomaly_hypotheses`、`anomaly_root_causes`。
- **不採用** ChatGPT 持久狀態 `尚未分析 / 待驗證 / 部分驗證 / 已確認`（`待驗證` 在本系統指對策有效性）。原因結論狀態沿用 `ANOMALY_ROOT_CAUSE_STATUSES`。
- ChatGPT「填原因後預設待驗證」→ **statement 非空且 status=`尚未開始` 時改存 `提案`**；帶入與儲存不得自動 `已驗證`。
- **分析紀錄 append-only**；`＋補充紀錄` →「加入」立即 `create_analysis_note`，日常路徑不與原因結論綁同一 transaction。
- **「帶入原因結論」** 不呼叫 `promote_hypothesis_to_root_cause`；只填同頁草稿；儲存時可帶 `promoted_from_hypothesis_id`。
- **Phase 6**：驗證區 auto-expand（`已驗證`/`無法確認`）、佐證參考唯讀摘要 + **前往附件**、derived 狀態提示；不新增「支持／不支持／證據不足」持久欄位。
- **Phase 7**：`can_leave()` 與工作台 tab 切換使用三鍵（**儲存並離開** / **不儲存** / **取消**）；僅 guard 路徑使用 `save_analysis_pending_changes` 單一 SQLite transaction；「加入」「儲存原因結論」維持既有單一 API + in-flight 防重複提交。

### ChatGPT 狀態 → 既有儲存映射

| ChatGPT UI 標籤 | 實作 |
|---|---|
| 尚未分析 | 空狀態文案（無 statement 且 status=`尚未開始`） |
| 待驗證（原因） | status=`提案` 或 `調查中` |
| 已確認 | status=`已驗證`（需 statement + 驗證欄位契約） |
| 無法確認 | status=`無法確認` + `not_established_reason` |
| 部分驗證 | **不持久化**（derived UI only） |
| 待驗證（overview） | 維持 `verification_result` = 對策有效性，不混用 |

## Non-Goals

- 新 CHECK 狀態、分析紀錄 edit/delete、AI 自動確認根因
- 8D / 處置項目 / 結案 / 匯出契約變更
- workbench visual baseline PNG 自動 promotion
- 以單一「儲存變更」取代「加入」+「儲存原因結論」的日常操作動線

## Progress

- [x] Phase 1：refresh 保留 tab／捲動／展開
- [x] Phase 2：原因結論同頁編輯 + 收合驗證 + 儲存
- [x] Phase 3：＋補充紀錄 inline
- [x] Phase 4：比較可能原因預設收合 + 列上操作
- [x] Phase 5：帶入原因結論 + `promoted_from_hypothesis_id`
- [x] Phase 6：佐證參考、驗證 auto-expand、derived 狀態提示
- [x] Phase 7：三鍵離開 guard、tab 切換 guard、bundle save、in-flight 防護
- [ ] Native workbench baseline promotion（需獨立核准）

## Verification

- Focused：`tests.test_anomaly_management_page`、`tests.test_anomaly_workbench_dialogs`、`tests.test_anomaly_workbench_repository`
- Native：`scripts/qt_visual_probe.py --target workbench`（PNG promotion 另核）
- `git diff --check`；不觸 `data/`

## Remaining work

- `workbench-page-analysis` baseline human review + promotion
