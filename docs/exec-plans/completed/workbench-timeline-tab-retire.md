# 工作台「處理歷程」分頁退役（方案 A）

**狀態**：已完成  
**日期**：2026-09-09

## 目標

退役產品層對案件工作台「處理歷程」Tab 與手動「新增處理紀錄」入口；工作台收成 4 分頁。

## 產品邊界

| 層級 | 行為 |
|------|------|
| Repository / SQLite | `anomaly_audit_logs` schema、migration、`append_anomaly_audit_log`、`list_anomaly_timeline` **保留** |
| 自動 audit 寫入 | `_case_action_service`、`_anomaly_service` 結案/重開/Action 狀態變更 **繼續寫入** `anomaly_audit_logs` |
| Service（產品 API） | `list_timeline` / `list_audit_logs` 回 `[]`；`append_manual_audit` fail-closed |
| UI | `AnomalyManagementPage` 四分頁：`案件概覽` / `Action 清單` / `根本原因` / `附件與佐證` |
| Visual probe | `workbench` 4 tab PNGs；`dialog-density` 移除 `add-audit` |

## SSOT

- `src/database/repo_helpers.py`：`RETIRED_WORKBENCH_TIMELINE_MSG`
- `src/services/event/_anomaly_workbench_service.py`：產品讀寫 fail-closed
- `src/ui/widgets/anomaly_management_page.py`：`TAB_NAMES` 四分頁

## 刻意保留

- `add_audit_log_dialog.py` 源碼檔未刪除；無產品 UI 入口
- Repository 層 timeline/audit 測試與 `test_workbench_phase4` 結案/重開 audit 覆蓋不變

## 驗證

```powershell
$env:PYTHONPATH='src;.'
$env:QT_QPA_PLATFORM='offscreen'
.venv\Scripts\python.exe -m unittest tests.test_anomaly_management_page tests.test_anomaly_workbench_write_dialogs tests.test_workbench_phase4 tests.test_anomaly_workbench_repository tests.test_layout_constants
scripts/harness_check.ps1
.venv\Scripts\python.exe scripts/qt_visual_probe.py --target workbench --min-width --scale 1.0,1.25,1.5
.venv\Scripts\python.exe scripts/qt_visual_probe.py --target dialog-density
```
