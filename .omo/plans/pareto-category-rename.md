# Pareto 異常分類文案精簡

## 目標

將 `ROOT_CAUSE_PARETO_OPTIONS` 中 10 項異常分類文案縮短為 2-8 字的「名詞+形容詞」口語化版本，保留原始定義邊界且彼此易於辨識。

## 原始 → 新文案對照

| # | 原始（11-13 字） | 新文案 |
|---|-----------------|--------|
| 1 | 製程條件/參數未受控 | 製程參數失控 |
| 2 | 文件/SOP/規格資料缺口 | 規範文件缺漏 |
| 3 | 檢驗/量測/出貨把關不足 | 檢驗把關失靈 |
| 4 | 設計/圖面/組裝匹配風險 | 設計匹配不良 |
| 5 | 治具/設備/工具能力不足 | 設備能力不符 |
| 6 | 包裝/搬運防護不足 | 包裝防護不足 |
| 7 | 物料/來料品質異常 | 來料品質不良 |
| 8 | 作業方法/訓練執行落差 | 標準作業不落實 |
| 9 | 供應商回覆/改善管理不足 | 供應商改善不力 |
| 10 | 其他/待釐清 | 其他 |

## TODO

- [x] **Step 1: Source 定義更新** — 修改 `src/ui/widgets/defect_form_widgets.py` 中 `ROOT_CAUSE_PARETO_OPTIONS` 列表的 10 項文案
  - `ANOMALY_CATEGORY_OPTIONS` 是同一物件參照，無需額外修改
  - `ROOT_CAUSE_CATEGORY_OPTIONS`（close_anomaly_dialog.py）也是同一參照，無需改動
  - ✅ LSP diagnostics clean — Python syntax OK

- [x] **Step 2: 測試檔更新** — 同步更新 2 個測試檔中的硬編碼期望值
  - `tests/test_anomaly_category_dropdown.py:test_category_dropdown_uses_root_cause_pareto_taxonomy()` — ✅ 更新完畢，1 passed
  - `tests/test_stats_view_anomaly_chart.py` line 227-228 — ✅ 更新完畢
  - 驗證：`python -m pytest tests/test_anomaly_category_dropdown.py -v -k "test_category_dropdown_uses_root_cause_pareto_taxonomy"` ✅

- [x] **Step 3: 全量驗證** — 跑完整測試套件確認無回歸
  - `test_anomaly_category_dropdown`: 1/1 ✅
  - `test_stats_view_anomaly_chart`: 14/14 ✅
  - `test_form_field_pairing_layout`: 7/7 ✅
  - LSP diagnostics clean on all changed files ✅

## 最終驗證

- [x] 以上 3 個 checkbox 全部完成
- [x] 確認 artifacts/ 下的歷史報表檔案不修改
- [x] 無任何 `as any` / `@ts-ignore` / `type: ignore` 殘留

## 不修改的檔案

- `artifacts/anomaly_root_cause_pareto_analysis_20260702.md` — 已產出的歷史報表 artifact，保留原始文案不回溯
