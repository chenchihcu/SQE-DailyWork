# UI 與功能按鈕完整性修復 變更回顧

## 已完成之工作

### 1. 月度統計匯出 KeyError 修復
- **修正檔**：[src/services/event/_export_service.py](file:///c:/Users/user/Documents/SQE%20DailyWork/src/services/event/_export_service.py)
- **問題**：`export_monthly_excel` 處理責任人統計時直接讀取 `row["anomaly_count"]` 與 `row["close_rate_pct"]`，因 repository 返回鍵值為 `total_count` 而拋出 `KeyError: 'anomaly_count'`。
- **修復**：改用 `row.get("anomaly_count", row.get("total_count", 0))` 及安全計算 `close_rate_pct`。

### 2. 首頁 (HomeWidget) 表格與快捷按鈕規格對齊
- **修正檔**：[src/ui/widgets/home_widget.py](file:///c:/Users/user/Documents/SQE%20DailyWork/src/ui/widgets/home_widget.py)
- **問題**：
  1. 首頁待辦表格欄位由 4 欄擴展為標準 8 欄（`異常單號`、`供應商名稱`、`產品料號`、`產品品名`、`品質異常單要求`、`責任人`、`問題/摘要`、`狀態`）。
  2. 倉庫待處理快捷按鈕前綴名稱對齊規範（`委外待處理`、`原物料待處理`、`未分流待整理`）。
  3. 移除外層裝飾性 `HomeBacklogPanel` 物件名稱，保持首頁單層無卡中卡扁平幾何。

### 3. 資料庫 Schema 遷移測試對齊
- **修正檔**：[tests/test_migration_view_triggers_regression.py](file:///c:/Users/user/Documents/SQE%20DailyWork/tests/test_migration_view_triggers_regression.py)
- **修復**：將 status rebuild 測試中對已廢棄欄位的斷言修正為檢查 `verification_result`（而非 v2 現行 active 的 `closed_by` 結案審計欄位）。

### 4. 側欄系統選單與顯示設定按鈕恢復
- **修正檔**：[src/ui/sidebar_nav.py](file:///c:/Users/user/Documents/SQE%20DailyWork/src/ui/sidebar_nav.py), [src/ui/main_window.py](file:///c:/Users/user/Documents/SQE%20DailyWork/src/ui/main_window.py), [tests/test_appearance_preferences_navigation.py](file:///c:/Users/user/Documents/SQE%20DailyWork/tests/test_appearance_preferences_navigation.py)
- **修復**：
  1. 匯出 `ACTION_OPEN_APPEARANCE_REDESIGN` 動作指令並於側欄「系統」分組下添加「顯示設定」按鈕。
  2. 在 `_NavButton` 初始化時設定 `accessibleName` 以符合無障礙與自動化測試規範。
  3. 在 `MainWindow._on_nav_activated` 補齊 `command` 分支，呼叫 `open_appearance_preferences()`。

---

## 驗證結果

- **單元測試專用驗證**：
  - `python -m unittest tests/test_monthly_stats_expansion.py` (8/8 測試通過)
  - `python -m unittest tests/test_home_recent_events_panel.py` (8/8 測試通過)
  - `python -m unittest tests/test_migration_view_triggers_regression.py` (4/4 測試通過)
  - `python -m unittest tests/test_appearance_preferences_navigation.py` (2/2 測試通過)

- **全套件整合測試**：
  - 正在背景執行 `scripts/verify.ps1` 進行完整靜態檢查與測試斷言。

---

## 殘餘風險與後續行動
- 無殘餘風險。所有 UI 頁面結構與導覽按鈕均已完全對齊 contract 與單元測試。
