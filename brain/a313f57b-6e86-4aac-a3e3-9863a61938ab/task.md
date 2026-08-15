# UI 與功能完整性修復任務追蹤

- [x] 修復 QueryWorkflowShell, CreateWorkflowShell, AnalyticsWorkflowShell 等結構導覽與 Panel 階層
- [x] 恢復 DefectList / DefectListWidget 欄位設定按鈕 (column_profile_button) 及重置按鈕 ("清除")
- [x] 修復 HomeWidget 8 欄表頭 ("異常單號", "供應商名稱", "產品料號", "產品品名", "品質異常單要求", "責任人", "問題/摘要", "狀態")
- [x] 修正 HomeWidget 倉庫待處理快捷按鈕前綴文字 ("委外待處理", "原物料待處理", "未分流")
- [x] 移除 HomeWidget 裝飾性雙層 HomeBacklogPanel 物件名稱
- [x] 修復 _export_service.py 中的 KeyError: 'anomaly_count' 匯出問題
- [x] 修復 test_migration_view_triggers_regression.py 舊欄位斷言 (verification_result)
- [x] 補全 sidebar_nav.py 及 main_window.py 的顯示設定 (ACTION_OPEN_APPEARANCE_REDESIGN) 指令導覽與選單開啟點
- [x] 執行 verify.ps1 全套件自動化測試驗證
