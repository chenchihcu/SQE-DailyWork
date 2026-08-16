# 2026-08-16 系統啟動效能優化、偏好設定 v5 契約擴充、表格排序與 PDF 中文字型支援

Plan status: completed

## Goal

- **啟動效能優化 (Startup Performance)**：消除程式啟動時因靜態匯入重量級第三方函式庫（`openpyxl`、`reportlab`、`matplotlib`）及重複資料庫查詢所造成的冷啟動延遲。
- **全域顯示與系統偏好設定 v5 (Preferences v5)**：擴充偏好設定為 5 大分頁（外觀主題、視覺表格與互動、表單業務預設、匯出與報告、系統與備份）共 27 個欄位，提供嚴格的型別校驗與平滑的 v1~v4 向下相容機制。
- **表格欄位自動排序 (Table Auto-Sorting)**：為系統內所有主要資料表（事件清單、不合格品清單、基礎資料等）提供支援多型比較的欄位點擊排序與排序狀態記憶。
- **ReportLab CJK 中文字型註冊 (PDF CJK Font)**：自動偵測並註冊 Windows 原生中文字型（微軟正黑體、新細明體等），確保 PDF 匯出時繁體中文完整渲染無缺字或方框。

## Key Architectural Decisions

1. **重量級套件延遲載入 (Lazy Loading)**：
   - 禁止在模組根層級靜態 `import openpyxl`, `import reportlab`, `import matplotlib`。
   - 建立 `src/ui/export_helpers.py` 封裝樣式與匯出輔助函式，樣式物件（如 `Font`, `PatternFill`, `Border`）改於函式內動態實例化並快取。
   - 建立 `src/ui/widgets/lazy_page_widget.py`（與 `EventCreatePage`）提供延遲容器掛載能力，僅在頁面首次 `showEvent` 時動態建構子表單。
   - 在 UI 層保留 `from ncr.services import export_service` 等模組級匯入，以維護 `unittest.mock.patch` 測試目標穩定性。

2. **偏好設定 v5 契約 (Appearance Preferences v5)**：
   - 命名空間鍵值：`ui_settings.appearance.preferences.v5`。
   - 5 大分頁架構：
     1. **外觀主題 (Appearance & Theme)**：頁面密度 (`density`)、側欄密度 (`sidebar_density`)、主題強調色 (`accent_color`: `electric_blue`/`slate_navy`/`emerald`/`amber`)、字體縮放 (`text_scale`)、高對比模式 (`contrast_mode`)。
     2. **視覺表格與互動 (Visual, Tables & Interaction)**：表格密度 (`table_density`)、交替行底色 (`alternating_row_colors`)、格線顯示 (`table_grid_lines`)、分頁筆數 (`table_page_limit`: 25/50/100/0)、動畫效果 (`enable_animations`)、雙擊行為 (`table_double_click_action`: menu/preview/edit)、搜尋模式 (`search_mode`: live/manual)、統計預設月份跨度 (`stats_default_span_months`: 3/6/12)、柏拉圖 80/20 門檻線 (`pareto_show_cutoff_line`)。
     3. **表單業務預設 (Form & Business Defaults)**：預設責任人 (`default_responsible_person`)、預設異常類別 (`default_anomaly_category`)、預設同步訪廠 (`default_sync_visit`)、預設到期天數 (`default_due_days`: 7/14/30)、預設訪廠時段 (`default_visit_time_slot`: 上午/下午/全天)。
     4. **匯出與報告 (Export & Reports)**：預設匯出目錄 (`default_export_dir`)、匯出完成動作 (`export_completion_action`: open_file/open_folder/notify_only)、報告組織抬頭 (`report_organization_header`)、匯出包含圖表 (`export_include_charts`)。
     5. **系統與備份 (System & Backup)**：預設啟動頁面 (`default_startup_page`: home/events/defects/stats)、關閉時自動備份提示 (`auto_backup_prompt`)、備份保留份數 (`backup_retention_count`: 5/10/20/30)、刪除前確認 (`confirm_on_delete`)。
   - 向下相容性：舊版 v1、v2、v3、v4 JSON 資料在記憶體中自動升級為 v5 預設值，不破壞舊資料。

3. **PDF CJK 字型註冊**：
   - 於 `src/services/event_pdf_exporter.py` 實作 `_register_cjk_fonts()`，優先尋找 Windows 字型目錄下的 `msjh.ttc`（微軟正黑體）、`mingliu.ttc`（細明體）或系統字型。
   - 註冊後使用 `MSJH` 或 `HeiseiKakuGo-W5` 作為字體樣式，避免 CJK 字元回退時報錯或呈現方框。

4. **資料庫保護**：
   - 全程維持 `data/sqe_v2.db` 資料庫結構與資料不動，所有設定僅透過 `ui_settings` 表進行鍵值存取。

## Verification

- 單元與合約測試：
  - `tests/test_appearance_preferences.py`
  - `tests/test_appearance_preferences_dialog.py`
  - `tests/test_layout_constants.py`
  - `tests/test_form_field_pairing_layout.py`
  - `tests/test_stats_view_anomaly_chart.py`
- 啟動與效能檢查：
  - 驗證啟動期間不靜態載入 openpyxl/reportlab/matplotlib。
- Harness 與語法檢查：
  - `scripts/harness_check.ps1`
  - `scripts/verify.ps1 -Profile Focused`
