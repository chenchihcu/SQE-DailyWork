# 2026-07-28 SQE DailyWork 品質修正計畫

Plan status: completed — P1/P2/U1/U2/U3/M1 程式修正與驗證已全數完成，資料庫保持不變

## Goal

- 消除 NCR 清單在換頁、變更每頁筆數、編輯與匯出時的資料定位不一致。
- 讓窄幅事件清單、建立異常同步訪廠提示、統計局部失敗的使用者行為可理解且可恢復。
- 以相容 facade 把高變動的查詢／分頁職責從大型 UI 與 repository 移出，且不改 v2 資料契約。

## Decisions

- 不執行正式資料庫 migration、刪欄、回填或資料修正；所有測試使用記憶體或 disposable snapshot。
- NCR 列表的畫面快取只保留目前頁；筆數、分頁、編輯與匯出一律共享同一個 filter query。
- 小於 `1024px` 時以「重點欄位檢視」維持可讀性，並提供明確按鈕切回完整欄位；不遺失任何資料欄位。
- 統計 service 的局部例外必須顯示「暫時無法載入」與重新整理行動，不能偽裝成「暫無資料」。

## Progress

| ID | Severity | Issue and root cause | Action | Status |
| --- | --- | --- | --- | --- |
| P1 | P1 | NCR 的 `PaginationBar` 可選每頁筆數，但畫面仍以固定 `NCR_ITEMS_PER_PAGE` 進行全量快取切片與編輯索引。 | 新增 query-backed `count_defects` / `get_defects_page`，抽出 `defect_list_paging`，改為目前頁資料定位與全量 query 匯出。 | completed |
| U1 | P2 | 事件清單在窄幅時同時呈現所有欄位，掃讀困難。 | 新增欄位 profile breakpoint、完整欄位切換、提示與回歸測試。 | completed |
| U2 | P2 | 新建異常首次開啟時，同步訪廠的說明 label 未初始化。 | 建構完成後立即更新提示。 | completed |
| U3 | P2 | 責任人／類別統計查詢失敗被呈現成空資料。 | 保留局部失敗狀態，顯示可重試的 error empty state。 | completed |
| M1 | P3 | `repository.py` 和 NCR 清單混有不相干 schema／分頁渲染職責。 | 以相容 private alias 抽出 SQLite schema helper，抽出 query-backed NCR mixin；公開呼叫點不變。 | completed |
| V1 | P2 | multi-DPI native Qt probe 截圖完成後沒有 JSON 回傳並卡住，無法形成正式視覺 gate。 | 修正 CP314 `.venv` 啟動與 probe 子程序收尾；每個 scale 單獨執行並保存 stdout JSON。 | completed |
| C1 | P2 / L3 | `closed_by` 歷史欄位備忘。 | 遵循專案制度維持資料庫不變，不執行破壞性 migration。 | completed |

## Verification

- 聚焦回歸：測試全數通過，覆蓋 NCR 分頁／編輯、NCR core、窄幅欄位、同步訪廠提示、統計部分失敗及 layout constants。
- `scripts\\verify.ps1 -Profile Focused`：compileall、focused contract tests、offscreen structural smoke 已通過。
- 原生 Windows Qt 截圖已產生 100%／125%／150% 的事件清單；確認重點欄位、提示與完整欄位按鈕無裁切、CJK 無方框。
