# 供應商事件作業佇列（精簡、不聯集）

Plan status: completed

## Goal

新增側欄三個供應商事件作業佇列（逾期未結、待根本原因、進行中處置），首頁改為佇列入口板，主管檢視移除作業清單分頁，避免未結案清單聯集重覆。

## Delivered

- `CASE_QUEUE_COLUMNS` / `CASE_QUEUE_RCA_COLUMNS` 與 `SupplierEventQueuePage`
- `manager_view_repository.get_supplier_event_queue_counts` + sidebar badge
- 首頁佇列 hub；倉庫捷徑不變
- 主管檢視僅案件總覽 + 單張 Excel
