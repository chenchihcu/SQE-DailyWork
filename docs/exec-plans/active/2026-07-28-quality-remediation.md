# 2026-07-28 SQE DailyWork 品質修正計畫

Plan status: active — P1/P2 程式修正已完成，L3 schema 與原生視覺 gate 待核准／重建

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
| V1 | P2 | multi-DPI native Qt probe 截圖完成後沒有 JSON 回傳並卡住，無法形成正式視覺 gate。 | 先修正 CP314 `.venv` 啟動與 probe 子程序收尾；每個 scale 單獨執行並保存 stdout JSON。 | pending |
| C1 | P2 / L3 | `closed_by` 仍在新建／重建 schema、repository 寫入與 detail select 中；現有 v2 契約與 migration regression 都要求它不存在。 | 需核准後才訂定相容 migration、snapshot 回歸與 rollback；本計畫不自行改 schema。 | blocked on approval |

## Verification

- 聚焦回歸：90 tests passed，覆蓋 NCR 分頁／編輯、NCR core、窄幅欄位、同步訪廠提示、統計部分失敗及 layout constants。
- `scripts\\verify.ps1 -Profile Focused`：compileall、focused contract tests、offscreen structural smoke 已通過；native belt 截圖後未正常收尾，不能判定整體 gate 通過。
- 原生 Windows Qt 截圖已產生 100%／125%／150% 的事件清單；可目視確認重點欄位、提示與完整欄位按鈕無裁切、CJK 無方框，但缺 JSON font/QSS evidence，狀態為 `not pass`。
- 擴大 migration regression 已確認 `closed_by` 契約不一致；未藉由修改 schema 來讓測試綠燈。

## Remaining work

1. **L3 approval required**：以 disposable snapshot 演練 `closed_by` 的新建 schema、重建 schema、repository／service 清理與 legacy payload 回歸；明確決定既有正式資料庫欄位的保留或受控移除策略後，才可變更 migration。
2. 修復 `.venv` CP314 launcher 與 `qt_visual_probe.py` multi-scale lifecycle；分別執行 `main`、`event-list`、`form-density` 的 100%／125%／150% native probe，逐次保存並檢核 JSON 的 `visual_trustworthy`、CJK font 與 QSS warning gate。
3. 以上兩項完成後，重跑完整 unittest、Focused gate、native visual belt 與 `git diff --check`；只在所有 required gates 通過後把本計畫移至 `completed/`。

## Rollback

- 已完成的程式變更可按檔案 diff 回復；不使用 destructive Git 指令。
- 未經使用者核准，不會寫入正式資料庫、執行 schema migration、刪除 `closed_by` 欄位或回復正式資料。
