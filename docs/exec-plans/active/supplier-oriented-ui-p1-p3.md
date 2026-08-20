# 供應商導向 UI 改造執行計畫（P1–P3）

Plan status: active

## 目的

將 SQE DailyWork 從功能頁面導向調整為供應商案件導向，同時維持供應商事件與倉庫不合格品的資料表、統計及匯出邊界分離。供應商 360 僅是唯讀聚合視角；任何資料契約變更都必須有 migration、回溯相容測試及文件同步。

## 階段

### P1：工作台與查詢動線

- 側欄移除四個事件 scope 一等列，改為事件管理頁內 scope chips。
- 首頁待辦優先呈現下一步處置、到期日、責任人與逾期狀態。
- 新增 Ctrl+K 全域唯讀搜尋，路由至既有事件、供應商及 NCR 頁面。
- 同步更新 UI 契約、測試與原生 Windows Qt 視覺基線。

### P2：供應商 360 與 NCR 關聯

- 為 `defect_records` 增加可為 NULL 的 `supplier_id`，依既有供應商名稱回填；無法唯一匹配者保留未關聯狀態。
- 建立供應商總覽與供應商 360 唯讀頁，時間軸聚合 anomalies、visits、defect_records，但每筆保留來源標籤，統計不混算。
- 由供應商主檔與建立頁提供進入 360、預選供應商及既有寫入流程的路由。

### P3：案件治理與報告

- 在異常管理頁加入六階段唯讀完成度 stepper。
- 由 NCR 編輯對話框以預填資料轉開供應商異常，新增來源 NCR 追溯欄位。
- 增加供應商評分卡的唯讀計算與季度 Excel 報告，報告內明確分列異常、訪廠及 NCR 來源。

## 驗證閘門

- Python 變更：執行聚焦 unittest，並在可行時執行 `scripts\verify.ps1`。
- UI 變更：offscreen 僅作結構 smoke；CJK、DPI、按鈕可見性使用原生 Windows `scripts\qt_visual_probe.py`。
- schema/migration：先備份資料，使用一次性 `migration_meta` 閘門，驗證新庫、既有庫與無法匹配資料。
- 每階段完成後同步 `AGENTS.md`、`docs/ui-layout-theme-contract.md`、`docs/architecture-workflow-contract.md` 及相關測試。

## 風險與限制

- 不把 NCR 寫入 supplier-event 表，也不把兩條來源合併為單一統計。
- 不使用名稱模糊匹配回填 `supplier_id`；零筆或多筆匹配都保留 NULL 並提供可追溯資訊。
- 不以新的落地統計表取代既有查詢服務。
