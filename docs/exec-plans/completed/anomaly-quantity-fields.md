# 供應商異常數量欄位補齊

## 狀態
已完成（2026-09-09）

## 目標
補齊供應商異常線「批量數／不良數／不良率」三欄，修正 NCR 轉開數量語意。

## 契約
- `batch_qty`：批量數（沿用欄位，標籤更名）
- `qty_inspected`：檢驗數（選填；>0 時作不良率分母）
- `qty_ng`：不良數（新增 DB 欄）
- `defect_rate`：唯讀計算 `qty_ng / 分母`（分母 = `qty_inspected` 若 >0，否則 `batch_qty`）
- NCR `qty` → `qty_ng`，不預填 `batch_qty` 或 `qty_inspected`

## 驗證
- `tests.test_event_manage_actions`
- `tests.test_anomaly_trace_fields`
- `tests.test_event_pdf_export`
- `scripts/qt_visual_probe.py --target event-create`
