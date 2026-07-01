# ui-ux-quality-improvement - Work Plan

## TL;DR (For humans)

**What you'll get:** SQE DailyWork 桌面程式的 UI/UX 品質提升 — 消除 NCR 模組與主程式之間的視覺不一致、統一分散的分頁元件、補齊載入狀態與無障礙標籤、讓必填欄位有統一的紅色星號標記。

**Why this approach:** 探索發現 NCR 模組（倉庫不合格品管理）有自己的 QSS 與版面常數，與主程式不相容，導致視覺落差。先合併共用資源（theme tokens、pagination、layout constants）再逐一補齊狀態與無障礙，每個修改都以原生 Qt 截圖驗證。

**What it will NOT do:** 不重新設計配色或品牌風格、不新增頁面或側欄項目、不改資料庫或後端邏輯、不引入第三方動畫庫。

**Effort:** Medium
**Risk:** Low - 每個變更都是純 UI 重構，有現有 layout constants 與 theme tokens 可對照，回滾明確
**Decisions I made for you:**
- 我決定 NCR 模組應該共用主程式的 theme tokens 而非自己維護一套 QSS → 這消除了不一致的根源
- 分頁元件統一為 PaginationBar → 消除重複實作與兩種樣式系統
- 載入狀態使用 QStatusBar 顯示訊息 → 最不侵入的方式
- 必填欄位用紅色星號標記 → 符合通用 UI/UX 規則

Your next move: Momus 高精度審查已完成（4 項 minor revision 已修正）。核准後即可開始執行。

---

> TL;DR (machine): Medium effort, Low risk — 8-component UI/UX quality pass: unify dual theme system, consolidate pagination, harden layout constants, add required-field markers, cover all display states, add accessible names, fix sidebar fragility, verify with native Qt screenshots.

## Scope
### Must have
1. NCR 模組 QSS 與主主題系統一致化（theme tokens 共用）
2. 分頁元件統一：消除 PaginationWidget，NCR 改引用 PaginationBar
3. NCR 頁面佈局常數改用 `layout_constants.py`
4. 必填欄位紅色 `*` 標記（defect_form、anomaly_dialog、visit_dialog）
5. 載入中／空白／錯誤／成功四狀態畫面補全（pages 切換、list 載入）
6. 互動元件 accessibleName 補全（sidebar、pagination、toolbar buttons）
7. 側欄間距改用動態計算（消除 `nav_layout.addSpacing(硬編碼數字)`）
8. 每項提交附原生 Windows Qt 視覺截圖驗證

### Must NOT have (guardrails, anti-slop, scope boundaries)
- 不更動整體配色方案或品牌設計語言
- 不改動資料庫 schema、service、repository 或匯出功能
- 不新增頁面或側欄導覽項目
- 不改動既有元件公有 API 簽章（只加不出）
- 不引入第三方 widget/動畫/圖示庫
- 每筆 commit 不得超過 250 行純程式碼（400 含空行註解）

## Verification strategy
> Zero human intervention - all verification is agent-executed.
- Test decision: tests-after + existing test suite (`scripts\verify.ps1`)
- Evidence: .omo/evidence/task-N-ui-ux-quality-improvement.png (native Qt screenshots)
- CI: `python scripts\qt_visual_probe.py --target main` for native screenshot capture

## Execution strategy
### Parallel execution waves
- Wave 1 (C1+C3): 主題整合 + 版面常數 — 互為相依
- Wave 2 (C2): 分頁元件合併 — 依賴 C1 完成
- Wave 3 (C4+C5): 必填標記 + 狀態補全 — 可並行
- Wave 4 (C6+C7): 無障礙 + 側欄間距 — 可並行
- Wave 5 (C8): NCR 模組視覺一致化 — 依賴 C1~C3, C5

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1. NCR 改引用主 theme_tokens | — | 2, 5 | 3 |
| 2. PaginationBar 統一 | 1 | 5 | 3 |
| 3. NCR 改用 layout_constants | — | 5 | 1, 2 |
| 4. 必填欄位星號標記 | — | — | 5, 6, 7 |
| 5. 狀態畫面補全 | 1 | — | 4, 6, 7 |
| 6. accessibleName 補全 | — | — | 4, 5, 7 |
| 7. 側欄間距動態化 | — | — | 4, 5, 6 |
| 8. NCR 模組完整視覺審查 | 1, 2, 3, 5 | — | 4, 6, 7 |

## Todos

- [ ] 1. **NCR 模組 QSS 改用主 theme_tokens 系統**
  What to do:
  - 修改 `src/ncr/ui/ui_style.py`：移除 `app_stylesheet()` 內的顏色/字型硬編碼（約 200 行），改從 `ui.theme_tokens` 與 `ui.theme_qss.get_theme_qss()` 匯入
  - 保留 NCR 特有樣式（如 `#defectTrackerTabs`）但顏色/間距改由 token 決定
  - 修改 `src/ncr/embed.py:58`：移除 `self.setStyleSheet(app_stylesheet())`，讓主 `get_theme_qss()` 統一覆蓋
  - 修改 `src/ncr/ui/defect_list.py`、`defect_form.py` 中直接 `setStyleSheet()` 的區塊改為 property-based QSS
  - 不得刪除 `app_stylesheet()` 函式；將其內部邏輯改為回傳空字串並以 `warnings.warn("deprecated")` 標記
  Parallelization: Wave 1 | Blocked by: — | Blocks: 2, 5
  References: `src/ui/theme.py:58` `src/ui/theme_qss.py:53` `src/ui/theme_tokens.py` `src/ncr/ui/ui_style.py` `src/ncr/embed.py:57-58`
  Acceptance criteria: 執行 `python -c "from ui.theme_qss import get_theme_qss; qss = get_theme_qss(); assert 'TOKENS' not in qss"` 確認 QSS 為 token 化。執行 `.\scripts\verify.ps1` 全部通過。
  QA scenarios:
  - Happy: `scripts\qt_visual_probe.py --target main` → 產生截圖，視覺無明顯 NCR 頁面樣式落差分界
  - Failure: `scripts\verify.ps1` 全部測試通過
  Evidence: `.omo/evidence/task-1-ui-ux-quality-improvement.png`
  Commit: Y | `refactor(ncr-theme): merge NCR QSS into main theme_tokens system`

- [ ] 2. **PaginationBar 統一為單一分頁元件**
  What to do / Must NOT do:
  - NCR 的 `PaginationWidget` (`src/ncr/ui/ui_style.py:1228-1314`) 應棄用，改由 `src/ui/widgets/pagination_bar.py`（PaginationBar）取代
  - 找到所有 `PaginationWidget` 的使用處（`src/ncr/ui/defect_list.py` 等），改用 `PaginationBar`
  - PaginationBar 若有缺失功能（如 `pageChanged` signal 名稱不同）則擴充 API 但保持向後相容
  - 不得刪除原始 PaginationWidget class，但透過 `warnings.warn("deprecated", DeprecationWarning)` 標記
  Parallelization: Wave 2 | Blocked by: 1 | Blocks: 5
  References: `src/ncr/ui/ui_style.py:1228-1314` `src/ui/widgets/pagination_bar.py:20-253` `src/ncr/ui/defect_list.py`
  Acceptance criteria: NCR defect_list 頁面使用 PaginationBar 且功能正常。`grep -r "PaginationWidget" src/ncr/` 回傳 0 匹配（棄用警訊息除外）。`.\scripts\verify.ps1` 全部通過。
  QA scenarios:
  - Happy: 啟動應用 → 切換到倉庫不合格品追蹤 → 確認分頁 Bar 出現，可正常點按
  - Failure: 測試 `pageChanged` signal 正確傳遞頁碼；grep 確認 PaginationWidget 未被新建實例
  Evidence: `.omo/evidence/task-2-ui-ux-quality-improvement.png`
  Commit: Y | `refactor(pagination): replace NCR PaginationWidget with shared PaginationBar`

- [ ] 3. **NCR 佈局常數改用 `layout_constants.py`**
  What to do:
  - 將 `src/ncr/ui/ui_style.py:38-50` 中的 `PAGE_MARGIN`/`SECTION_SPACING`/`FIELD_SPACING_X`/`FIELD_SPACING_Y`/`LABEL_MIN_WIDTH`/`INPUT_HEIGHT`/`BUTTON_HEIGHT` 等常數改為 import from `ui.layout_constants`
  - 若 `layout_constants.py` 缺少對應數值則擴充該檔案（而非在 NCR 保留副本）
  - 修改 `src/ncr/embed.py:41` 的 `(8, 16, 8, 0)` → `PAGE_OUTER_MARGINS`
  - 修改 `src/ncr/ui/defect_form.py` 中各處硬編碼 margins 改為對應常數
  - 修改 `src/ncr/ui/defect_list.py:124,129` 等硬編碼
  - 修改 `src/ncr/ui/ui_style.py:979,986,1001,1016,1241` 等硬編碼
  - Must NOT: 不改動 `DIALOG_OUTER_MARGINS` 等已有常數的數值語意
  Parallelization: Wave 1 | Blocked by: — | Blocks: 5
  References: `src/ui/layout_constants.py` `src/ncr/ui/ui_style.py:38-50` `src/ncr/embed.py:40-42` `src/ncr/ui/defect_form.py:140,324,728,733` `src/ncr/ui/defect_list.py:124,129`
  Acceptance criteria: NCR 頁面不再定義自己的 margin/spacing 常數，全部引用 `layout_constants.py`。`.\scripts\verify.ps1` 全部通過。
  QA scenarios:
  - Happy: `scripts\qt_visual_probe.py --target main` → 頁面間距與主頁面一致（24px outer margins）
  - Failure: grep for `PAGE_MARGIN\s*=`, `SECTION_SPACING\s*=` in `src/ncr/` — 應為 0 匹配
  Evidence: `.omo/evidence/task-3-ui-ux-quality-improvement.png`
  Commit: Y | `refactor(ncr-layout): use shared layout_constants instead of local copies`

- [ ] 4. **必填欄位統一的紅色星號標記**
  What to do / Must NOT do:
  - 在 `src/ui/widgets/common_widgets.py` 新增一個 `RequiredFieldLabel` class：在 QLabel 文字右側附加紅色 `*`，維持相同的 `setProperty("role", ...)` 機制
  - 在 `src/ncr/ui/defect_form.py` 中將 `return_slip_type`、`qty`、`item_no`、`defect_desc` 等必填欄位標籤改為 `RequiredFieldLabel`
  - 在 `src/ui/widgets/new_anomaly_dialog.py` 中識別並標記必填欄位
  - 在 `src/ui/widgets/new_visit_dialog.py` 中識別並標記必填欄位
  - 不得變更現有 tooltip 行為，星號為額外視覺提示
  - Must NOT: 使用 emoji ⭐❌ 代替，只用純文字 `*` 或專用 QLabel
  Parallelization: Wave 3 | Blocked by: — | Blocks: —
  References: `src/ncr/ui/defect_form.py:332-336` `src/ui/popup_i18n.py` `src/ui/widgets/new_anomaly_dialog.py` `src/ui/widgets/new_visit_dialog.py`
  Acceptance criteria: 所有必填欄位旁顯示紅色 `*`。`.\scripts\verify.ps1` 全部通過。
  QA scenarios:
  - Happy: `scripts\qt_visual_probe.py --target form-density` → 截圖中必填欄位星號清晰可見
  - Failure: 檢查新增的 RequiredFieldLabel 在表單 resize 後不破版
  Evidence: `.omo/evidence/task-4-ui-ux-quality-improvement.png`
  Commit: Y | `feat(ui): add RequiredFieldLabel with red asterisk marker`

- [ ] 5. **載入/空白/錯誤/成功四狀態畫面補全**
  What to do / Must NOT do:
  - 在 `src/ui/main_window.py:_switch_primary_page:195-206` 中，當觸發 lazy load 時在 `statusBar()` 顯示「載入中...」訊息
  - 若 `refresh_data()` 拋出例外，在 `EmptyStateWidget` 顯示錯誤訊息而非靜默失敗
  - 檢查所有 `EmptyStateWidget` 使用處：確保空白、錯誤、成功狀態各自有不同提示文字
  - 在 `src/ui/widgets/home_widget.py:246-277` 的 `refresh_data()` catch 區塊中確保錯誤訊息顯示於 UI 而非只有 logger
  - 在 `src/ui/widgets/event_list_filter_mixin.py:213-221` 中為 `_update_empty_state` 加上篩選後的空白與載入失敗兩種文字
  - Must NOT: 不引入 QProgressBar 或第三方程式庫；維持輕量 QStatusBar 與 EmptyStateWidget 模式
  Parallelization: Wave 3 | Blocked by: 1 (main_window imports) | Blocks: —
  References: `src/ui/main_window.py:195-206` `src/ui/widgets/home_widget.py:246-277` `src/ui/widgets/event_list_filter_mixin.py:213-221` `src/ui/widgets/common_widgets.py:312-332` (EmptyStateWidget)
  Acceptance criteria: 頁面切換時 statusBar 顯示「載入中...」；資料為空顯示 EmptyStateWidget；錯誤時顯示紅底錯誤訊息。`grep -c "EmptyStateWidget" src/ui/widgets/home_widget.py src/ui/widgets/defect_list_widget.py src/ncr/ui/defect_list.py` 每個檔案至少回傳 1。`.\scripts\verify.ps1` 全部通過。
  QA scenarios:
  - Happy: 切換每個頁面 → 確認載入訊息、空白狀態、錯誤狀態皆有畫面
  - Failure: 模擬 DB 連線失敗 → 確認錯誤訊息顯示於 UI
  Evidence: `.omo/evidence/task-5-ui-ux-quality-improvement.png`
  Commit: Y | `feat(ui): cover loading/empty/error/success display states`

- [ ] 6. **互動元件 accessibleName 補全**
  What to do / Must NOT do:
  - 在 `src/ui/sidebar_nav.py:_make_nav_btn:337-348` 中為每個 `_NavButton` 加上 `setAccessibleName(label)`
  - 在 `src/ui/widgets/pagination_bar.py:_setup_ui:79-118` 中為 `first_btn`/`prev_btn`/`next_btn`/`last_btn` 加上 `setAccessibleName("第一頁"/"上一頁"/"下一頁"/"最後一頁")`
  - 在 `src/ui/widgets/pagination_bar.py:187` 中為動態產生的頁碼按鈕加上 `setAccessibleName(f"第 {page_no} 頁")`
  - 在 `src/ui/sidebar_nav.py:322-333` 的 footer 快速建立按鈕上加上 accessible labels
  - 若元件已有 ToolTip 且內容與 accessibleName 相同，可直接使用 `setAccessibleName(self.toolTip())`
  - Must NOT: 不重複設定已有 tooltip 的 QLabel（非互動元件）
  Parallelization: Wave 4 | Blocked by: — | Blocks: —
  References: `src/ui/sidebar_nav.py:337-348` `src/ui/widgets/pagination_bar.py:79-118,187` `src/ui/sidebar_nav.py:322-333` `ui-ux-universal.md §5`
  Acceptance criteria: 所有 sidebar nav buttons 與 pagination buttons 皆有 `accessibleName`。`.\scripts\verify.ps1` 全部通過。
  QA scenarios:
  - Happy: 執行 `python -c "from accessible_check import check"` (若無此工具則手動檢查)
  - Failure: grep for `setAccessibleName` count 應 ≥ interactive widget count
  Evidence: `.omo/evidence/task-6-ui-ux-quality-improvement.txt` (grep 結果)
  Commit: Y | `feat(a11y): add accessibleName to all interactive widgets`

- [ ] 7. **側欄間距改用動態計算**
  What to do / Must NOT do:
  - 修改 `src/ui/sidebar_nav.py:232`：移除 `nav_layout.addSpacing(SIDEBAR_NAV_ITEM_HEIGHT + _NAV_GROUP_GAP * 2)`，改用動態插入空 _NavButton 或 `QSplitter`，使間距不依賴硬編碼
  - 修改 `src/ui/sidebar_nav.py:288`：Logo section margins `(16, 10, 16, 8)` → 引用 `layout_constants` 對應常數（若無則擴充）
  - 使用 `_NAV_GROUP_GAP = 12` (已在檔案上方定義) 作為 QSS 變數的後備
  - Must NOT: 改變側欄整體寬度 `SIDEBAR_WIDTH = 220` 或 `SIDEBAR_NAV_ITEM_HEIGHT = 44`
  Must NOT: 不引入 QSizePolicy 與既有排版邏輯衝突
  Parallelization: Wave 4 | Blocked by: — | Blocks: —
  References: `src/ui/sidebar_nav.py:187-260` `src/ui/layout_constants.py:43-46`
  Acceptance criteria: 側欄視覺上一致，無間距異常。增減側欄項目時間距自動適應。`.\scripts\verify.ps1` + `tests/test_top_nav_compact_height.py` 通過。
  QA scenarios:
  - Happy: `scripts\qt_visual_probe.py --target main` → 側欄各區塊間距均勻
  - Failure: 修改 _OVERVIEW_ITEMS 長度測試間距回應
  Evidence: `.omo/evidence/task-7-ui-ux-quality-improvement.png`
  Commit: Y | `refactor(sidebar): replace hardcoded nav spacing with dynamic layout`

- [ ] 8. **NCR 模組完整視覺一致性驗證**
  What to do / Must NOT do:
  - 在前 7 個任務完成後，啟動應用程式進行完整視覺走查
  - 對照 `ui-ux-universal.md` 與 `AGENTS.md §3 UI/UX & Styling Standards` 逐項檢核：
    - NCR pages 的 QSS 與主程式一致（按鈕、表單、表格、標籤）
    - NCR 的 CJK 字型與主程式相同
    - 間距、色調符合 layout_constants 與 theme_tokens
    - 必填欄位標記、狀態畫面、載入回饋已補全
    - 所有 clickable 元件在 hover/focus 時有視覺回應
  - 使用 `scripts\qt_visual_probe.py` 進行原生截圖
  - 若發現不一致則記錄為殘餘風險
  - Must NOT: 不做屬於 Scope OUT 的修改（不改配色/db/export）
  Parallelization: Wave 5 | Blocked by: 1, 2, 3, 5 | Blocks: —
  References: `ui-ux-universal.md` `AGENTS.md §3` `src/ncr/embed.py` `src/ncr/ui/` (all files)
  ### Residual risk: R3 — 截圖僅限 100% DPI；ui-ux-universal §11 要求 100%/125%/150% 各檢視一次。若時間允許，應在三個 DPI 各執行一次 `qt_visual_probe.py`。
  Acceptance criteria: 截圖確認 NCR 頁面與主頁面無視覺落差。`.\scripts\verify.ps1` 全部通過。
  QA scenarios:
  - Happy: `scripts\qt_visual_probe.py --target main` + `--target form-density` → 三張截圖每頁面
  - Failure: 逐一比對 NCR vs main 頁面的 QSS token 使用一致
  Evidence: `.omo/evidence/task-8-ui-ux-quality-improvement-{front,form,list}.png`
  Commit: Y | `chore(ncr-qa): final visual consistency verification`

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [ ] F1. Plan compliance audit: 確認每項 todo 的 acceptance criteria 達成，evidence 存在
- [ ] F2. Code quality review: 確認無 scope creep，無 CSS 硬編碼新增，無 API 破壞
- [ ] F3. Real manual QA: 實際啟動應用程式走查每個頁面（透過 `scripts\qt_visual_probe.py` 原生截圖）
- [ ] F4. Scope fidelity: 對照 Scope OUT 確認未越界

## Commit strategy
- 每個 todo 一個獨立 commit，共 8 個 commits
- Commit message 格式: `<type>(<scope>): <summary>` (見各 todo 的 Commit 欄位)
- 依序完成，無 squash 需求（每個 commit 獨立可審閱）
- 若有重工修正，使用 `fixup!` 標記後在最終 rebase

## Success criteria
1. `scripts\verify.ps1` 全部通過
2. NCR 與主頁面使用同一份 QSS token（無 `setStyleSheet` 覆蓋主主題）
3. 所有可互動元件有 accessibleName
4. 必填欄位有紅色 `*` 標記
5. 頁面切換時顯示載入回饋、空白/錯誤狀態各具專屬畫面
6. 側欄間距不依賴硬編碼數字
7. 原生 Windows Qt 截圖（100% DPI）顯示所有狀態
