---
slug: ui-ux-quality-improvement
status: awaiting-approval
intent: unclear
pending-action: user approval → ready for execution
approach: 探索代碼庫後，識別 8 個獨立 UI/UX 元件層面的品質議題，依相依性排序逐步改善
---

# Draft: ui-ux-quality-improvement

## Components (topology ledger)
| id | outcome | status | evidence path |
|---|---|---|---|
| C1 主題整合 | 消除雙重 QSS 系統，NCR 模組共用主 theme_tokens | active | `src/ui/theme_qss.py` vs `src/ncr/ui/ui_style.py` |
| C2 分頁元件合併 | 消除 PaginationWidget/PaginationBar 重複實作 | active | `src/ui/widgets/pagination_bar.py` vs `src/ncr/ui/ui_style.py:1228` |
| C3 版面常數硬編碼修正 | NCR 頁面改用 PAGE_OUTER_MARGINS 等共用常數 | active | `src/ncr/embed.py:41`, `src/ncr/ui/ui_style.py:38-50` vs `src/ui/layout_constants.py` |
| C4 表單必填欄位視覺標記 | 統一紅色星號標記必填欄位 | active | `src/ncr/ui/defect_form.py:332-336` (tooltip only) |
| C5 載入/空白/錯誤狀態補全 | 所有頁面具備載入中/空白/錯誤/成功四種畫面 | active | `src/ui/main_window.py:195` (無載入回饋) |
| C6 無障礙 (Accessibility) | 互動元件補 accessibleName，focus ring 確認 | active | `src/ui/sidebar_nav.py` (icon buttons 缺) |
| C7 側欄間距脆弱 | 取代手動 spacing 計算 | active | `src/ui/sidebar_nav.py:232` |
| C8 NCR 模組視覺一致化 | NCR 缺發狀態、tooltip、Dirty tracking 完整性 | active | `src/ncr/ui/` 各檔案 |

## Open assumptions (announced defaults)
| assumption | adopted default | rationale | reversible? |
|---|---|---|---|
| NCR 模組應共用主程式 theme_tokens | 移除 `app_stylesheet()` 改由 `get_theme_qss()` 統一覆蓋 | 雙 QSS 導致視覺不一致，維護成本加倍 | 是（保留原檔案可 rollback） |
| 分頁元件合併為 PaginationBar | 保留 `src/ui/widgets/pagination_bar.py`，NCR 改引用此元件 | PaginationBar 已用 role/variant pattern 設計 | 是 |
| 必填欄位以紅色 `*` 標示 | 使用 QLabel 疊加 asterisk 圖示／文字 | ui-ux-universal.md §2 要求統一標記 | 是 |
| 載入狀態用 QStatusBar 訊息 | 使用 `statusBar().showMessage()` 與`setEnabled(False)` | 最低侵入性，不需新增 spinner widget | 是 |
| AccessibleName 逐一補上 | `setAccessibleName()` on all interactive widgets | ui-ux-universal.md §5 要求 | 是 |
| NCR 常數改引用 layout_constants | NCR 的 PAGE_MARGIN/SECTION_SPACING 改用 main 常數 | 消除重複定義 | 是 |

## Findings (cited - path:lines)

1. **Dual theme system**: `src/ui/theme_qss.py:53` (get_theme_qss) provides role/variant-based tokens;
   `src/ncr/ui/ui_style.py` has its own `app_stylesheet()` (~200 lines). `src/ncr/embed.py:58` applies
   it via `self.setStyleSheet(app_stylesheet())` on DefectTrackerPage, overriding main theme.
   
2. **Two pagination widgets**: `src/ui/widgets/pagination_bar.py:20` (PaginationBar, 234 lines) vs
   `src/ncr/ui/ui_style.py:1228` (PaginationWidget, 86 lines). Different style patterns (`role`/`variant`
   vs `uiRole`/`set_button_role`). Different API surface.

3. **NCR hardcoded layout values**: `src/ncr/embed.py:41` uses `(8, 16, 8, 0)` instead of
   `PAGE_OUTER_MARGINS = (24, 24, 24, 24)`. `src/ncr/ui/ui_style.py:38-50` defines its own
   `PAGE_MARGIN = 8`, `SECTION_SPACING = 22`, `FIELD_SPACING_X = 20` etc., duplicating
   `src/ui/layout_constants.py`.

4. **Required fields lack visual markers**: `src/ncr/ui/defect_form.py:332-336` uses only tooltip
   text ("必填欄位") but no red asterisk. ui-ux-universal.md §2 requires unified visual marker.

5. **No loading state**: `src/ui/main_window.py:195-206` lazy-loads pages via `hasattr(widget, "_has_loaded")`
   without showing any loading indicator. `refresh_data()` may block UI.

6. **Accessibility gaps**: Sidebar `_make_nav_btn` `src/ui/sidebar_nav.py:337-348` and pagination
   `PaginationBar._setup_ui` `src/ui/widgets/pagination_bar.py:79-118` lack `setAccessibleName()`.
   ui-ux-universal.md §5 requires accessible labels on icon-only/interactive elements.

7. **Fragile sidebar spacing**: `src/ui/sidebar_nav.py:232` hardcodes
   `nav_layout.addSpacing(SIDEBAR_NAV_ITEM_HEIGHT + _NAV_GROUP_GAP * 2)` for alignment
   — brittle when items change. Logo section `src/ui/sidebar_nav.py:288` uses hardcoded
   `(16, 10, 16, 8)` instead of layout constants.

8. **NCR `defect_form.py` has two layout sets**: `src/ncr/ui/defect_form.py:140` uses
   `DIALOG_OUTER_MARGINS` (imported), but `:324` hardcodes `(16, 12, 16, 12)` for inline form,
   `:728` hardcodes `(0, 0, 0, 0)`, `:733` hardcodes `(22, 20, 22, 20)` — 5 different margin
   values in the same file. No single source of truth.

## Decisions (with rationale)

1. **NCR 模組逐步併入主主題系統**：先讓 NCR QSS 讀取主 theme_tokens 而非複製數值，下階段再完整移除 `app_stylesheet()`。
2. **PaginationBar 為唯一分頁元件**：保留較新的 role/variant 版，NCR 改引用。
3. **CJK 字重維持 400/700**：現有 theme_qss 已使用 700 用於標題，符合 ui-ux-universal.md §6 規範。
4. **載入回饋以 `statusBar().showMessage()` 為預設**：不引入第三方動畫，維持現有 QStatusBar 機制。
5. **分批次提交，每個完成項附視覺截圖驗證**：因桌面 Qt 不可用 offscreen 當視覺證據。

## Scope IN

1. 主程式 QSS 與 NCR QSS 的一致性（theme tokens 共用）
2. PaginationBar 統一元件（消除 PaginationWidget）
3. NCR 頁面佈局常數改用 `layout_constants.py`
4. 必填欄位紅色 `*` 標記
5. 載入中／空白／錯誤／成功四狀態畫面補全
6. 互動元件 `accessibleName` 補全
7. 側欄間距改用動態計算
8. 附視覺截圖的原生 Qt 驗證

## Scope OUT (Must NOT have)

- 不重新設計整體配色或設計語言（不改 DESIGN.md）
- 不引入新的第三方 widget／動畫庫
- 不改動資料庫 schema、service 邏輯或匯出功能
- 不新增頁面或側欄項目
- 不改造匯出報告（PDF/Excel/PPTX）的視覺呈現
- 不批量修改既有元件的 API 簽章

## Open questions

（由 UNCLEAR 路徑自動解析，無遺留問題）

## Approval gate
status: awaiting-approval
<!-- Exploration 完成，findings 已記錄。等待使用者核准後寫入完整計劃檔。 -->
