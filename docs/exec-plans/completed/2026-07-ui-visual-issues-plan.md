# UI 視覺/互動問題審查計劃

**日期**: 2026-07-04
**範圍**: 全專案 UI layer（src/ui/, src/ncr/ui/）
**性質**: 只調查 + 計劃，不立即修復

---

## 調查方式

1. 原始碼靜態分析（codegraph、grep、直接閱讀）
2. 對照 AGENTS.md/README.md/docs/ui-layout-theme-contract.md 契約
3. 比對 ui-ux-universal.md 通用規則

---

## 發現 A — 死 QSS：KPI 卡片遺留樣式

| 項目 | 位置 | 嚴重度 |
|------|------|--------|
| `KpiCard` class 已無任何實體使用 | src/ui/widgets/common_widgets.py:169 | High |
| QSS 為 kpiCard/kpiValue/kpiTitle 服務約 20 個選擇器 | src/ui/theme_qss.py:72-199 | High |

**RCA**: HomeWidget KPI panel 已退役（2026-06-30 UI IA simplification），但 KpiCard class 與其 QSS 樣式未被清理。

**證據**:
- `KpiCard` 在 common_widgets.py 定義但 grep 不到任何 import 或實體化
- `role="kpiCard"` 的 QSS 覆蓋 default/hover/focus/danger/info/success/pending 七種狀態
- `role="kpiValue"` 與 `role="kpiTitle"` QSS 亦無對應 widget

**建議修復**:
1. 移除 `src/ui/widgets/common_widgets.py` 中 KpiCard class
2. 移除 `src/ui/theme_qss.py` 中所有 `[role="kpiCard"]`、`[role="kpiValue"]`、`[role="kpiTitle"]` 選擇器
3. 若 `TYPOGRAPHY["kpi_value"]` 不再使用，一併移除

---

## 發現 B — Sidebar 標籤不一致：`不合格品統計` vs `不合格品統計分析`

| 位置 | 使用名稱 |
|------|----------|
| src/ui/sidebar_nav.py:65 | `不合格品統計` |
| src/ui/main_window.py:84 (PAGE_META) | `不合格品統計` |
| src/ui/widgets/ncr_stats_widget.py:90 (source tag) | `倉庫不合格品統計` |
| src/ui/widgets/ncr_stats_widget.py:358 (dialog title) | `不合格品統計匯出設定` |
| README.md | `不合格品統計分析` |
| docs/ui-layout-theme-contract.md | `不合格品統計分析` |

**RCA**: 2026-07-01 UI IA simplification 將倉庫統計頁命名為 `不合格品統計分析`，但 sidebar_nav.py 與 main_window.py 仍使用舊名。source tag 與 dialog title 也與契約不一致。

**建議修復**:
1. `sidebar_nav.py:65` → `不合格品統計分析`
2. `main_window.py:84` → `不合格品統計分析` (PAGE_META short title)
3. `ncr_stats_widget.py:90` source tag → `倉庫不合格品統計分析`
4. `ncr_stats_widget.py:358` dialog title → `不合格品統計分析匯出設定`

---

## 發現 C — 側欄 Icon 重複無區分（視覺掃描性）

| 側欄群組 | 項目 | Icon |
|----------|------|------|
| 供應商事件 | 單獨異常/訪廠發現異常/訪廠紀錄/已結案 | 全部 `anomaly.svg` |
| 倉庫不合格品 | 建立不合格品/待處理委外加工/待處理原物料 | 全部 `warehouse.svg` |

**RCA**: 四項供應商事件 scope 共用同一 icon，三項倉庫 pending 頁面亦共用。違反 ui-ux-universal §3 可掃描性原則 — 使用者在側欄無法一眼區分不同 scope。

**建議修復**（選擇其一）:
- A: 為每個 scope 建立專用 icon（推薦，掃描性最佳）
- B: 在文字前方加入簡短區分標示（如 `[已結案]` prefix）
- C: 僅 `單獨異常` 保留 badge，其餘項目以文字樣式差異區分

---

## 發現 D — NCR ui_style.py font-weight 違規

| 位置 | 行號 | 違規值 | 正確值 |
|------|------|--------|--------|
| src/ncr/ui/ui_style.py | 259 | `font-weight: 800` | `font-weight: 700` |

**RCA**: AGENTS.md 與 tests/test_theme_typography_consistency.py 要求 CJK 環境下 QSS 只使用 400/700，800 在 Windows CJK 渲染不一致。

**建議修復**: 改為 `font-weight: 700`

---

## 發現 E — theme_qss.py 過大（1378 行）

| 指標 | 數值 |
|------|------|
| 檔案行數 | 1378 |
| 選擇器數量 | ~200+ |
| 單一 `get_theme_qss()` f-string | 整份文件 |

**RCA**: 所有 QSS 集中於一個巨型 f-string，違反單一模組 250 LOC 的鬆散建議，且難以維護。單次 import 即編譯整份 QSS（部分未使用）。

**建議修復**: 拆分為 3-4 個主題區塊（core/reset、form/table、chart/sidebar、ncr），在 `get_theme_qss()` 中組合。

---

## 發現 F — `defect_form_widget.py` vs `defect_form_widgets.py` 命名混淆

| 檔案 | 行數 | 用途 |
|------|------|------|
| `src/ui/widgets/defect_form_widget.py` | 33 | 相容性 re-export shim（僅 import/export） |
| `src/ui/widgets/defect_form_widgets.py` | 322 | 實際 widget（ProductSectionEditor、TechTransferCard 等） |

**RCA**: 原始檔案 split 後保留 shim，但名稱相差僅一個 's'，容易造成 import 混淆。

**建議修復**: 將 shim 重新命名為 `defect_form_shim.py`，明確標示其相容性角色（API 保持不變）。

---

## 發現 G — 超大型模組（>1000L，需關注）

| 檔案 | 行數 |
|------|------|
| src/database/repository.py | 5737 |
| src/services/event_service.py | 1501 |
| src/ui/theme_qss.py | 1378 |
| src/ncr/ui/ui_style.py | 1219 |
| src/ncr/ui/defect_form.py | 1214 |
| src/ncr/tests/test_core.py | 1214 |
| src/services/pdf_html_helpers.py | 923 |

**RCA**: 這些檔案包含多個不同職責的邏輯。repository.py 5737 行尤其顯著 — 單一檔案涵蓋 anomaly/visit/product/supplier/NCR 等多組 CRUD。

**建議修復**: 分階段重構（需要個別 plan，不在此範圍內）。

---

## 發現 H — TYPOGRAPHY token 遺留

| Token | 使用狀態 | 說明 |
|-------|----------|------|
| `kpi_value` (26px) | QSS 仍有使用 (theme_qss.py:181) | KPI card 值字級 |
| `kpi_title` (13px) | QSS 仍有使用 (theme_qss.py:161) | KPI 標題字級 |
| `hero_title` (24px) | 無 QSS 使用 | hero banner 已退役 |
| `hero_subtitle` (13px) | 無 QSS 使用 | hero banner 已退役 |
| `hero_meta` (12px) | 無 QSS 使用 | hero banner 已退役 |
| `nav_tab` (13px) | QSS 仍有使用 (theme_qss.py:380) | 舊版 scope tab bar |
| `divider_title` (16px) | QSS 仍有使用 (theme_qss.py:269) | 舊版分隔標題 |
| `kpi_title` (13px) | QSS 仍有使用 | 同 kpi_value 遺留 |

**建議修復**:
1. 先處理發現 A（移除 KPI QSS），確定哪些 token 不再使用
2. 移除 `hero_title/hero_subtitle/hero_meta`（無任何 QSS 使用）
3. `kpi_value`/`kpi_title` 隨發現 A 一併處理
4. `nav_tab`、`divider_title` 需確認 QSS 使用情境

---

## 發現 I — Hero Banner Token 存活於 TOKENS dict

```python
"hero_gradient_start": _P["hero_start"],
"hero_gradient_mid": _P["hero_mid"],
"hero_gradient_end": _P["hero_end"],
"hero_title_color": _P["text_inverse"],
"hero_subtitle_color": _P["on_hero_subtitle"],
"hero_meta_text": _P["on_hero_meta"],
```

Hero banner 已於 2026-06-07 UI IA consolidation 退役，但這些 token 仍存活於 `theme_tokens.py`。PALETTE key 若也無其他用途可移除。

---

## 執行順序建議

| 優先序 | 議題 | 預估工時 | 相依 |
|--------|------|----------|------|
| P0 | B — sidebar 標籤不一致 | 0.5h | 無 |
| P0 | D — font-weight 800 違規 | <0.25h | 無 |
| P1 | A — KPI 死 QSS + 發現 H token 清理 | 1h | 需確認無其他 KPI 用途 |
| P2 | C — sidebar icon 區分 | 1-2h | P0 (B) 完成後 |
| P2 | I — hero token 清理 | 0.5h | 先確認 PALETTE key 狀態 |
| P3 | F — shim 檔案更名 | 0.25h | 無（但需更新所有 import） |
| P3 | E — theme_qss.py 拆分 | 2-3h | P1 (A) 完成後 |
| P4 | G — 超大型模組重構 | 各需獨立 plan | P0-P2 完成後 |

## 驗證 Gate

| 驗證項 | 方法 |
|--------|------|
| QSS 無錯誤 | `scripts/qt_visual_probe.py` 確認 `qss_unknown_property_warnings == 0` |
| CJK 字型 | `cjk_font_ok` + `ncr_cjk_font_ok` + `pdf_cjk_font_ok` 皆 true |
| Sidebar 顏色角色 | `--target main` 原生截圖 |
| 標籤一致性 | grep 確認所有 `不合格品統計分析` 用字一致 |
| 佈局無回歸 | `tests/test_layout_constants.py` 綠燈 |
| font-weight 無違規 | `tests/test_theme_typography_consistency.py` 綠燈 |

---

## 視覺 QA 驗證結果（2026-07-05）

**方式**: 原生 Windows Qt `scripts/qt_visual_probe.py` 9 個 target（多 DPI 1.0/1.25/1.5x、min-width 1024）+ Sonnet-5 多代理視覺審查（對抗式 verify，18 agents / 5 confirmed / 5 refuted）+ 聚焦測試。所有截圖 `visual_trustworthy=true`、`qss_unknown_property_warnings=0`。

### 計劃修復項驗證（已實作 + 原生 Qt 證據通過）

| 發現 | 項目 | 驗證結果 |
|------|------|----------|
| A | KpiCard 死 QSS 移除 | ✅ grep 零殘留（`kpiCard/KpiValue/KpiTitle`）|
| B | sidebar `不合格品統計分析` | ✅ `sidebar_nav.py:65` + `main_window.py:86`；1.0/1.5x 截圖完整不裁切 |
| C | sidebar icon 區分 | ✅ 新增 `outsource.svg`/`material.svg`；委外加工/原物料 icon 不再相同 |
| D | NCR font-weight 800→700 | ✅ 原始碼零 `font-weight 500/600/800`；`test_theme_typography_consistency` + `test_font_source_single_truth` 綠燈；NCR 建立表標題常規粗體 |
| E | theme_qss.py 拆分 | ✅ 6 個 `_qss_*.py` 組裝，9 面向 `qss_warn==0` |
| F | shim 更名 `defect_form_shim.py` | ✅ App 匯入正確；探針已同步 |
| I | hero token 清理 | ✅ grep 零殘留（`hero_*`）|

### 本次額外修復

| 項目 | 檔案 | 說明 |
|------|------|------|
| 探針過時匯入 | `scripts/qt_visual_probe.py:459-461` | `SupplierFormDialog` 改由 `supplier_form_dialog.py` 匯入（重構後 `master_data_widget` 不再 re-export），解除 `form-density` 崩潰 |
| **發現 J**：分頁列高 DPI 擁擠 | `defect_list_widget.py`（分頁移獨立列）+ `pagination_bar.py`（4px 末字護欄）| 事件管理工具列單列塞不下 source-tag + 584px `PaginationBar` + 3 動作鈕，窄寬/高 DPI 下標籤重疊裁切；分頁改獨立 full-width 列後 1.0/1.5x 皆完整 |

### 既有、非本次重構造成（低優先、未修）

| Sev | 項目 |
|-----|------|
| P3 | 側欄 badge（6/4/8）無 pill/chip 樣式，僅右對齊數字 |
| P3 | active 列無底色填充，僅左側藍色指示條 + 粗體 |
| P3 | 聚焦欄位首字被文字游標 caret 方塊覆蓋（RCA：移開焦點即消，非 QSS 重構造成）|

### 對抗式驗證駁回的誤報（5）
柏拉圖資料標籤碰撞、累積線遮擋、圖例分離、空狀態 ×2（judge 誤把已填表當空表）— 圖表與空狀態實際乾淨。

### 回歸測試
48 個聚焦測試綠燈：`test_pagination_button_text_visibility`、`test_layout_edge_alignment`、`test_micro_interactions`、`test_event_list_widget_render_stability`、`test_master_data_query_behavior`、`test_home_recent_events_panel`、`test_color_polish_ui_smoke`、`test_layout_constants`、`test_theme_typography_consistency`、`test_font_source_single_truth`。`harness_check.ps1` passed。
