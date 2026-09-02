# 側欄依定義改名並全庫對齊

Plan status: completed

## Goal

將供應商事件側欄五項改為定義導向名稱（事件查詢／逾期案件／根因待查／處置項目／案件總覽），
匯出概況欄 `進行中處置數` → `處置項目數`；PAGE_KEY、COUNT SQL、stack index 不變。

## Delivered

- `src/ui/sidebar_nav.py`：`NAV_LABEL_*` SSOT、tooltip、處置項目圖示改 `anomaly.svg`
- `src/ui/main_window.py`：`_PAGE_TITLES` 引用 SSOT
- 佇列 banner／空狀態、案件總覽頁、source tag、status_colors、偏好核取文案
- `OVERVIEW_FIELDS` + Excel/PDF 匯出欄名 SSOT；manager 匯出訊息
- README、AGENTS、architecture/ui-layout 契約、visual-qa/ui spec、CHANGELOG

## Verification

- Focused unittest（nav、queues、exports、event list render、appearance dialog）
- `scripts/harness_check.ps1`
- Native `qt_visual_probe.py --target main|manager-view|event-list`（建議）
