# Risk Ledger (SQE DailyWork)

| Scope | Risk | Guardrail | Next action (Owner=self) | Revalidation gate | Rollback | Status |
|:---|:---|:---|:---|:---|:---|:---|
| Data/Visit Records | 新增 `visit_product_sections` / `visit_defect_notes` 後，既有單產品訪廠可能顯示不一致 | 保留 `visits.product_id/product_name/...` snapshot；`create_schema()` backfill 舊訪廠為一筆產品區段；repository tests 覆蓋 legacy payload | 下次正式匯入/開啟既有資料庫時確認訪廠列表與 PDF | `scripts\verify.ps1` + legacy DB smoke open | 回退 repository/UI/PDF/docs 變更，保留 DB 備份 | Active |
| UI/Stats | 數據點密集時標籤產生重疊 (Label Overlap) | 1. 調小字級至 9pt<br>2. 保留 Tooltip 詳情作為冗餘顯示 | 若使用者反應遮擋嚴重，實作標籤碰撞檢測或僅顯示 Top 10 | 使用者驗證 (UAT) | 撤銷 `stats_view_widget.py` 中 `setPointLabelsVisible(True)` 之修改 | Active |
| UI/Stats | 渲染效能 (Rendering Performance) | QtCharts 原生優化 | 監控極大數據量（>50 點）時的流暢度 | 壓力測試 | 移除標籤顯示 | Low |
