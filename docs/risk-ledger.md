# Risk Ledger (SQE DailyWork)

| Scope | Risk | Guardrail | Next action (Owner=self) | Revalidation gate | Rollback | Status |
|:---|:---|:---|:---|:---|:---|:---|
| Data/Visit Records | 新增 `visit_product_sections` / `visit_defect_notes` 後，既有單產品訪廠可能顯示不一致 | 保留 `visits.product_id/product_name/...` snapshot；`create_schema()` backfill 舊訪廠為一筆產品區段；repository tests 覆蓋 legacy payload | 下次正式匯入/開啟既有資料庫時確認訪廠列表與 PDF | `scripts\verify.ps1` + legacy DB smoke open | 回退 repository/UI/PDF/docs 變更，保留 DB 備份 | Active |
| UI/Stats | 數據點密集時標籤產生重疊 (Label Overlap) | 1. 調小字級至 9pt<br>2. 保留 Tooltip 詳情作為冗餘顯示 | 若使用者反應遮擋嚴重，實作標籤碰撞檢測或僅顯示 Top 10 | 使用者驗證 (UAT) | 撤銷 `stats_view_widget.py` 中 `setPointLabelsVisible(True)` 之修改 | Active |
| UI/Stats | 渲染效能 (Rendering Performance) | QtCharts 原生優化 | 監控極大數據量（>50 點）時的流暢度 | 壓力測試 | 移除標籤顯示 | Low |
| UI/Stats/Period Filter | 篩選元件更換後，無法單月篩選 | 起訖年月為真實可見控制，允許相同月份；已移除以 dummy proxy 當功能證據的假設 | 維持同月、反向區間與原生 popup 回歸 | `test_date_range_and_export_warnings.py` + native popup belt | 回復 period-control helper | Mitigated |
| UI/Anomaly No | 手動編輯異常單號可能造成重複或格式錯亂 | Repository 單一 validator 強制 11 碼純數字、日期前綴、唯一性；UI 保留即時提示 | 收集使用者實務操作回饋 | `test_anomaly_no_insert_retry.py` + `test_anomaly_repository_invariants.py` | 回復 repository validator 與相關 UI wiring | Mitigated |
| Data/Backup And Verification | WAL raw copy 或測試直連正式庫會遺漏資料或造成正式資料變更 | SQLite online backup + read-only integrity/count parity；`SQE_DB_PATH` 單一解析；verification disposable guard | 每次 full gate 確認來源 hash/mtime/counts 未變 | `test_database_backup.py` + `test_database_isolation.py` + `scripts\verify.ps1` | 停止驗證；保留 Phase 0 快照，未經核准不還原正式庫 | Mitigated |
| Data/Legacy Migration | 逐筆錯誤後仍標記 migration 完成會永久漏資料 | 單一 transaction、錯誤 rollback、不寫 completion metadata、輸出 reconciliation | 只在拋棄式 legacy fixture 重跑 | `test_migration_atomicity.py` | 回復 migration phase；正式庫不得執行 | Mitigated |
| Data/Product Ownership | 一筆正式異常的 supplier/product 歸屬無法從現有 master data 唯一判定 | 不自動修正；輸出 `Outputs/audit/*VERIFY.csv` 供人工分類 | 使用者確認歸屬後另開受控資料修正 | 正式庫唯讀 reconciliation query | 不適用；目前未寫入 | Active / VERIFY |
| Data/Phase0 Raw Hash | Phase 0 與結案的正式庫 raw hash 不同，但所有業務列一致；差異僅兩筆衍生月快取 `updated_at`，且結案值較早，現有證據無法唯一歸因 | 不自動還原、不寫正式庫；以 read-only row parity、integrity、當前 hash 穩定性保留證據 | 若需追查，先確認是否有外部程式同時開啟 DB，再以 Phase 0 快照做受控 cache reconciliation | Phase 0 snapshot 對正式庫逐表唯讀比較 | 未經使用者核准不還原 | Accepted residual / no live write |
| UI/Native Visual Gate | theme、probe target 或 baseline 漂移會讓單測／visual gate 假綠燈 | manifest-driven target mapping、缺 baseline 失敗、正式 theme 測試、Windows 100/125/150% belt | UI 變更後更新並人工檢視 baseline | `qt_visual_belt.py` + `qt_visual_regress.py` + harness mapping | 回復 UI helper／baseline 變更 | Mitigated |
