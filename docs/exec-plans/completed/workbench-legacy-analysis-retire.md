# 工作台 Legacy 分析／假設／8D 退役

**狀態**：已完成  
**日期**：2026-09-09

## 目標

完整退役產品層對以下三類工作台功能的讀寫與投影：

- 分析紀錄（`anomaly_analysis_notes`）
- 多層原因假設（`anomaly_hypotheses`）
- Supplier 8D 審查（`anomaly_eight_d_reviews`）

SQLite schema、migration 與 repository 低層 CRUD **保留**（冷存／稽核腳本仍可用）。

## 產品邊界

| 層級 | 行為 |
|------|------|
| Repository | CRUD 與 `hypothesis_overview_metrics` 保留；`get_anomaly_overview_card` 不再投影 `has_analysis_notes` / 假設指標 |
| Service（產品 API） | 讀取退役 API 回 `[]`；寫入 `raise ValueError(RETIRED_WORKBENCH_FEATURE_RETIRED_MSG)` |
| Timeline / 變更紀錄 | 過濾 `RETIRED_WORKBENCH_AUDIT_ACTIONS` |
| 匯出 / PDF / Markdown | 移除假設章節與 overview 假設欄位 |
| 附件面板 | 移除「關聯分析紀錄」「關聯假設」；Supplier 8D 僅透過 `category=Supplier 8D` |
| Quick Review | 「開放 Action」摘要 + `HANDLER_VIEW_ACTIONS` 深連結至工作台 Tab「Action 清單」 |

## SSOT

- `src/database/repo_helpers.py`：`RETIRED_WORKBENCH_AUDIT_ACTIONS`、`is_retired_workbench_audit_action()`
- `src/services/event/_anomaly_workbench_service.py`：產品讀寫 fail-closed

## 刻意保留

- Dialog 源碼檔（`anomaly_note_dialog.py` 等）未刪除；無產品 UI 入口
- `_append_hypothesis_export_sheet` 等死碼可於後續 code-simplifier pass 清除

## 驗證

```powershell
$env:PYTHONPATH='src;.'
$env:QT_QPA_PLATFORM='offscreen'
.venv\Scripts\python.exe -m unittest tests.test_anomaly_management_page tests.test_event_quick_review tests.test_anomaly_attachment_panel tests.test_exports_phase7 tests.test_anomaly_workbench_repository tests.test_hypothesis_phase3 tests.test_layout_constants
scripts/harness_check.ps1
```
