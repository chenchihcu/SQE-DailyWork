# 自動計算與防呆缺口補齊

## 狀態
已完成（2026-09-09）

## Goal
補齊開案日不可未來、單號自動重算偏好、同供應商追蹤號重複擋存、以及選填檢驗數作為不良率分母。

## Decisions
- 開案日（供應商異常 + NCR）日曆上限 = 今天。
- `auto_fill_anomaly_no_on_date_change=False` 時改日期不覆寫單號；新建仍預覽一次。
- 同供應商同追蹤欄同非空值 → 拒絕儲存；不還原 UNIQUE INDEX；舊列 grandfather。
- `qty_inspected` 選填；>0 時作不良率分母，否則用 `batch_qty`。

## Progress
- [x] 資料層 qty_inspected + 分母 SSOT
- [x] 追蹤號 duplicate 擋存
- [x] UI 日曆 / 偏好 / 檢驗數欄
- [x] 測試 + native visual probe

## Verification
- `tests.test_anomaly_quantity_fields` — 7 OK
- `tests.test_event_manage_actions` — qty_inspected 分母與上限 OK
- `tests.test_anomaly_trace_fields` — migration / validator OK
- `tests.test_poka_yoke_auto_calc` — 6 OK
- `scripts/qt_visual_probe.py --target event-create` — `visual_trustworthy: true`, `cjk_font_ok: true`, `qss_unknown_property_warnings: 0`
- `scripts/qt_visual_probe.py --target workbench` — 同上

## Remaining work
無。
