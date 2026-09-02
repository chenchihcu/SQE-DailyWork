---
name: sqe-dailywork-ui-ux-flow-optimizer
version: 1.2.0
description: 用於 SQE DailyWork 表單佈局密度、雙欄配對、操作動線最佳化、單一連續表單消除切頁摩擦、工具列緊湊化、多頁面 Context 連貫性、Workflow Shell 結構守衛、鍵盤 Tab 焦點流、Safe Key Fallback、唯讀高度防護與 Qt SizePolicy 陷阱防護。Use this skill 當要重構 UI 佈局、提升表單空間利用率、消除操作切頁摩擦或最佳化動線時。觸發詞包含「UI最佳化」「表單排版」「操作動線」「雙欄配對」「佈局密度」「節省空間」「UX flow」「form layout」「layout density」「動線」「WorkflowShell」「結構守衛」「切頁摩擦」「連續表單」。
allowed-tools: Read, Grep, Glob, Bash
---

# SQE DailyWork UI/UX 佈局與操作動線最佳化技能

本技能專門指導 SQE DailyWork 桌面應用程式之 UI/UX 空間利用率、表單排版密度、操作動線連貫性、架構外殼（Workflow Shell）結構合規、消除切頁摩擦之單一連續表單模式與 Qt 版面引擎避坑規範。

**Visit 產品 UI 已退役**（`docs/exec-plans/completed/retire-visit-product-line.md`）。勿復活 visit dialog、visit scope 或 Supplier 360 visit 分頁。

---

## 1. 表單排版與欄位配對原則 (Form Density & Pairing)

1. **禁止獨立空標籤按鈕行**：
   - 絕不要使用 `form.addRow("", self.btn_manage)` 讓輔助按鈕獨占整行並留下左側空白。
   - 應將按鈕以水平佈局（`QHBoxLayout`）緊湊嵌入主欄位右側（如 `contact_name_input` + `btn_manage_contacts`）。
2. **語意互補欄位雙欄配對**：
   - 凡業務上具有高度關聯的短欄位，應使用 `make_paired_form_row()` 或 `QGridLayout` 合併為雙欄配對列（例如：`主供應商 + 次要供應商`、`日期 + 時段`、`料號 + 工單`、`抽樣數量 + 已技轉`）。
   - 節省垂直高度，避免表單過度拉長導致不必要的滾動條。
3. **長文字欄位獨立直向展開**：
   - 多行文字框（如「活動摘要」、「問題描述」）應給予獨立欄位或右側專屬直欄，避免硬塞在標題下方造成高度壓縮。
4. **自訂行高與唯讀文字框高度防護**：
   - 唯讀問題描述區（如結案視窗、歷史檢視）不可設定過大的固定高度（例如 >120px），必須使用 `CLOSE_DIALOG_PROBLEM_MIN_HEIGHT = 120` 或依內容動態調整，防止擠壓主要輸入區。
   - 自訂文字輸入組件缺少 `document()` 時，應使用 `TEXT_EDIT_FALLBACK_LINE_HEIGHT = 22` 與 `TEXT_EDIT_FALLBACK_PADDING = 20` 進行標準行高換算，禁止任意硬編碼乘數。

---

## 2. 消除切頁摩擦與單一連續表單模式 (Single Continuous Form & Zero-Tab Friction)

1. **執行型對話框禁止濫用 QTabWidget**：
   - 在任務完成型/審查型對話框（如 `CloseAnomalyDialog` 異常結案、驗收審核對話框）中，**嚴禁**使用 `QTabWidget` 強迫使用者在「填寫改善 measures」與「上傳照片/佐證附件」兩個分頁間來回切換。
2. **單一連續可滾動佈局結構 (Unified Continuous Flow)**：
   - 應採用標準的單一連續卡片流：
     ```
     ┌────────────────────────────────────────────────────────┐
     │ 頂部：緊湊原始問題對照框 (CLOSE_DIALOG_REF_MARGINS)     │
     ├────────────────────────────────────────────────────────┤
     │ 中間：改善內容輸入 + 字數計數 + 結案日期 (QFormLayout)   │
     ├────────────────────────────────────────────────────────┤
     │ 下方：現場照片與改善佐證附件編輯器 (AttachmentEditor)     │
     ├────────────────────────────────────────────────────────┤
     │ 底部：固定動作列 (儲存 / 取消) (apply_dialog_layout)    │
     └────────────────────────────────────────────────────────┘
     ```
   - 讓使用者在單一視圖內完成「對照問題 → 輸入改善 → 檢視/附加照片 → 送出結案」，消除跨分頁記憶負擔與切頁摩擦。

---

## 3. 多分頁與彈出視窗 Context 連貫性 (Context Continuity)

1. **動作頁面直接對照原始問題**：
   - 執行頁籤上方必須提供緊湊唯讀的原始問題描述卡片（`CloseAnomalyProblemRef`），使用 `CLOSE_DIALOG_REF_MARGINS = (12, 8, 12, 8)`。
2. **語意標題層級一致性**：
   - `QLabel[role="sectionTitle"]` 僅用於一級區塊分界（例如：基本資訊、技轉）。二級欄位標籤使用一般 `QLabel`，避免破壞主題階層與測試斷言。
3. **消除無效空白佔位框**：
   - 彈出視窗頂部（如 `NewAnomalyDialog` / `CloseAnomalyDialog`）不可留置全空的 Frame，應設定為具備 `QLabel[role="title"]` 的 `DIALOG_HEADER_HEIGHT = 44` 緊湊主題 Header。

---

## 4. 工具列緊湊化與 Qt SizePolicy 陷阱 (Toolbar Compaction & SizePolicy Trap)

1. **整合次級切換至工具列**：
   - 消除孤立的第 4 列控制列，將視圖切換按鈕（如 `column_profile_button`）與狀態提示整合至 `toolbar_row`，為下方資料表格釋放最大垂直顯示空間。
2. **防範 QLabel 撐開 Layout 最小寬度陷阱**：
   - **問題**：在水平佈局（`QHBoxLayout`）中加入帶有長說明的 `QLabel` 時，Qt 預設會計算極大的 `minimumSizeHint`（例如 468px），導致整個工具列與視窗最小寬度被撐大（超過 1024px），破壞緊湊模式偵測與視窗縮放。
   - **解法**：在工具列內的文字標籤必須設定：
     ```python
     label.setWordWrap(True)
     label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
     ```

---

## 5. Workflow Shell 結構守衛與零視覺包袱模式 (Workflow Shell Hierarchy & Zero-Visual-Penalty Pattern)

1. **Workflow Shell 架構角色標誌**：
   - 系統包含三大工作流外殼標誌類別：
     - `QueryWorkflowShell`：用於事件查詢清單與 NCR 追蹤清單。
     - `CreateWorkflowShell`：用於事件建立與 NCR 建立表單。
     - `AnalyticsWorkflowShell`：用於統計分析頁面。
   - 這些外殼類別是 `test_surface_usage_structure.py` 與系統層級契約定位頁面角色的依據（透過 `findChild(WorkflowShell)` 驗證）。
2. **嚴禁破壞性移除外殼類別**：
   - 在重構或最佳化 UI 時，**絕不可刪除或遺漏**上述外殼類別，否則會引發全域結構測試回歸。
3. **零視覺包袱模式 (Zero-Visual-Penalty)**：
   - 為嚴格遵循「禁止卡中卡 (No Card-in-Card Over-Nesting)」的簡約設計規範，當頁面需保持單層扁平幾何但必須滿足 Shell 測試契約時：
     - 模式 A（隱藏子代理）：在主 Widget 初始化時建立隱藏外殼實例，例如 `self.workflow_shell = AnalyticsWorkflowShell(self); self.workflow_shell.hide()`。
     - 模式 B（輕量結構封裝）：將外殼作為內部結構容器，但佈局邊距設為 0，且不設定額外外層陰影或裝飾邊框。

---

## 6. 業務欄位與鍵名防禦性存取 (Safe Key Fallback & Boundary Standard)

1. **字典鍵值安全存取**：
   - 在報表匯出、圖表渲染與資料轉換層（如 `_export_service.py`），嚴禁直接以強制鍵名索引（如 `row["anomaly_count"]`）。
   - 必須使用安全回退鏈：`row.get("anomaly_count", row.get("total_count", 0))`。
2. **衍生指標除零防護**：
   - 結案率等衍生數值計算必須具備防護機制：
     ```python
     close_rate = row.get(
         "close_rate_pct",
         round((row.get("closed_count", 0) * 100.0 / row.get("total_count", 1)) if row.get("total_count") else 0.0, 1)
     )
     ```

---

## 7. 鍵盤導航焦點流 (Tab Order Alignment)

1. **視覺閱讀流與焦點鏈一致**：
   - 表單在初始化完成後，必須透過 `setTabOrder()` 明確串接焦點順序，嚴格依照「由上至下、由左至右」的視覺網格排列，避免多欄切換時焦點跳躍。

---

## 8. 單一佈局常數真相與覆蓋矩陣 (Single Source of Layout Truth & Coverage Matrix)

1. **嚴禁硬編碼像素**：
   - 所有 margin, padding, spacing, height, width 必須引用 `src/ui/layout_constants.py`。
   - 數值契約由 `tests/test_layout_constants.py` 固定。
2. **全系統核心常數覆蓋表**：
   - **間距與格線**：
     - `CONTROL_ROW_SPACING = 8`：工具列、按鈕列、水平操作列標準間距。
     - `ROW_GAP = 8`：表單列標準垂直間距。
     - `FORM_VERTICAL_SPACING = 12`：表單區段與容器垂直間距。
     - `COMPACT_PAGE_SPACING = 6`：緊湊卡片與行內小組件間距。
   - **對話框與卡片**：
     - `DIALOG_HEADER_HEIGHT = 44`：對話框固定標題列高度。
     - `DIALOG_FOOTER_CLOSE_MIN_WIDTH = 88`：關閉按鈕標準最小寬度。
     - `DIALOG_HEADER_FOOTER_H_MARGIN = 16`：Header/Footer 左右外距。
     - `DIALOG_BODY_MARGINS = (16, 14, 16, 10)`：對話框內容主體邊距。
     - `DIALOG_CARD_MARGINS = (16, 12, 16, 12)`：對話框內部卡片邊距。
     - `CLOSE_DIALOG_REF_MARGINS = (12, 8, 12, 8)`：問題參考卡邊距。
     - `CLOSE_DIALOG_PROBLEM_MIN_HEIGHT = 120`：唯讀問題描述區高度上限。
   - **通用與裝飾組件**：
     - `EMPTY_STATE_MARGINS = (24, 32, 24, 32)`：空狀態佔位框邊距。
     - `BRAND_DIVIDER_MARGINS = (0, 6, 0, 4)` / `BRAND_DIVIDER_SPACING = 5`：品牌分隔線。
     - `TEXT_EDIT_FALLBACK_LINE_HEIGHT = 22` / `TEXT_EDIT_FALLBACK_PADDING = 20`：自訂行高備用計算。
   - **篩選與搜尋限制寬度**：
     - `FILTER_STATUS_COMBO_WIDTH = 112`
     - `FILTER_MONTH_INPUT_WIDTH = 104`
     - `FILTER_SUPPLIER_MIN_WIDTH = 170`
     - `MASTER_SEARCH_MIN_WIDTH = 220` / `MASTER_SEARCH_MAX_WIDTH = 340`

---

## 9. 導覽與表單建立入口守衛 (Navigation & Create Entrypoint Guard)

1. **建立入口守衛**：
   - 供應商事件「新增異常」僅由側欄 `新增異常` 進入全頁 `EventCreatePage`；事件查詢工具列不得恢復冗餘 `新增異常` 或「新增訪廠」按鈕。
   - 若清單工具列仍有建立按鈕 helper（例如 `DefectListWidget._build_new_event_buttons()`），不得因 `mode == "query"` 而無意回傳 `None, None` 導致其他模式回歸。
2. **四重對齊導覽契約 (Quadruple Navigation Contract)**：
   - 新增或恢復頁面導覽時，必須同時完成以下四處對齊，缺一不可：
     1. **側欄定義**：在 `sidebar_nav._NAV_GROUPS` 中宣告語意鍵與圖示。
     2. **堆疊掛載**：在 `main_window.py` 定義明確的堆疊常數索引並透過 `stack.addWidget()` 掛載。
     3. **標題與防護**：在 `_switch_primary_page` 標題字典與 `_check_page_leave_dirty_guard` 納入防護。
     4. **跳轉方法**：實作 `open_new_*_page()` 或 `open_supplier_event_ops()` 等導覽方法並串接側欄點擊信號。
3. **表單送出有效性契約 (`can_submit` Protocol)**：
   - 凡嵌入至 `EventCreatePage` 或 `CreateWorkflowShell` 的表單組件（如 `NewAnomalyDialog`），必須實作 `can_submit(self) -> bool`。
   - `can_submit()` 應檢查關鍵必填資料（如 `supplier_id` 與 `product_id`），讓外殼的儲存按鈕能在表單無效或初始未選擇時精準維持禁用狀態。

---

## 10. `/grill-me` 互動需求釐清指南 (Interactive Grill-Me Clarification Protocol)

當使用者以 `/grill-me` 提出 UI 表單遺失、入口路徑缺失或操作動線改善時，應依循以下結構主動提問以釐清需求：
1. **入口層級與位置**：確認是要恢復左側側欄一等導覽列（全域快速切換）、清單頂部工具列按鈕（情境工作流入口）、抑或是兩者同步提供？
2. **工作流呈現形式**：確認建立表單應採用全頁式外殼（`EventCreatePage`，適合深度輸入與大表單）或彈出式對話框（Modal Dialog，適合快速填寫）？
3. **切頁摩擦與分頁結構**：確認對話框是否包含多個關聯維度（如改善 + 附件照片），優先推薦單一連續垂直滾動流（避免 QTabWidget 分割操作動線）。
4. **連帶連動契約**：確認是否需要支援未儲存離開防護（Dirty Guard）與送出後跳轉清單行為？Visit 產品線已退役，勿設計 visit 關聯同步。

---

## 11. CI 自動化驗證命令矩陣 (Automated Verification Matrix)

修改 UI 佈局、工作流外殼、表單動線或導覽路徑後，必須執行以下驗證：
1. **版面常數釘住測試**：`python -m unittest tests/test_layout_constants.py`
2. **建立頁與輕量入口導覽測試**：`python -m unittest tests/test_lightweight_visit_entry_routing.py`
3. **導覽列與標籤完整性測試**：`python -m unittest tests/test_top_nav_compact_height.py tests/test_ncr_embedding_smoke.py`
4. **結構合規測試**：`python -m unittest tests/test_surface_usage_structure.py`
5. **微互動與按鈕測試**：`python -m unittest tests/test_micro_interactions.py`
6. **佈局密度測試**：`python -m unittest tests/test_form_field_pairing_layout.py`
7. **月度統計匯出測試**：`python -m unittest tests/test_monthly_stats_expansion.py`
8. **導覽與啟動頁測試**：`python -m unittest tests/test_top_nav_compact_height.py tests/test_appearance_preferences_navigation.py`
9. **原生視覺探針**：`python scripts/qt_visual_probe.py --target form-density` 與 `python scripts/qt_visual_probe.py --target event-create --scale 1.0,1.25,1.5 --min-width`
10. **檢查探針指標**：`visual_trustworthy == True` 且 `qss_unknown_property_warnings == 0`。

---

## 12. 5 大介面重構與純淨統計守衛 (5 Core UX Refactoring Guards)

1. **Guard-Bottom-Action-Bar (底部操作列方案 A 守衛)**：
   - 建立與編輯全頁表單（`CreateWorkflowShell` / `DefectFormWidget`）必須將主要操作按鈕置於表單/卡片的最底端。
   - 排列嚴格遵循方案 A：左側為次要動作（`清除 / 重置`），右側為主要流程（`返回清單` + 主要 `儲存` 按鈕），頂部僅保留純文字標題與副標題。
2. **Guard-Itemized-Description (條列式逐條審閱動線守衛)**：
   - 缺失記錄、不良現象描述、確認事項與待追蹤清單一律採用 `BulletListWidget` 條列結構（動態序號 + 單行輸入 + 刪除 + `+ 新增條目`）。
   - 支援 `Enter` 快速換行新增下一列，底層相容 `\n` 換行字串，滿足逐條審查的工作習慣。
3. **Guard-Zero-Noise-Charts (統計純淨化無雜訊守衛)**：
   - 異常事件統計與 NCR 統計頁面僅保留「篩選區間」、「重新整理」、「匯出 Excel」以及核心統計圖表（月度趨勢圖、柏拉圖等）。
   - 移除或隱藏所有自動生成的大段文字分析與診斷摘要區塊（`insight_panel` / `info_banner`），維持乾淨直觀的視覺看板體驗。
4. **Guard-Horizontal-Subtabs (橫向子標籤與無捲軸排版守衛)**：
   - 事件查詢頁以 `EVENT_QUERY_SCOPE_TABS` 兩個水平 scope chip（單獨異常 / 已結案）切換資料範圍，並以狀態 `QComboBox`（全部 / 待處理 / 已結案）篩選；已結案 chip 鎖定狀態為已結案。
   - 表格高度與 SizePolicy 必須維持視窗自適應，消除內部與外層雙重垂直滾動條。
5. **Guard-Form-Iconography (表單語意圖示視覺強化守衛)**：
   - 表單區塊標題與重要欄位組群引入語意圖示（📋 基本/基礎資訊、🔍 不良現象/問題描述、⚙️ 技轉查核/處理狀態、📝 活動摘要、📊 風險與統計、📌 待追蹤事項），提升視覺掃讀層次與辨識效率。

---

## 13. 排版幾何對齊、表格寬度與 CJK 控制項守衛 (Alignment, Sizing & CJK Rendering Guards)

1. **Guard-CJK-Radio-Direction (CJK 單選與核取按鈕排版守衛)**：
   - 嚴禁對包含 CJK 中文字元的 `QRadioButton` 或 `QCheckBox` 呼叫 `setLayoutDirection(Qt.LayoutDirection.RightToLeft)`。
   - Windows Qt 下該設定會導致幾何反轉，使圓圈指標 `●` 直接覆蓋在文字字元上方（呈現 `?有 ●`、`?用 ○`）。一律維持標準 `LeftToRight`，透過卡片寬度與列數分配（如每列 3 張）調節佈局。
2. **Guard-Table-Column-Width-Scale (表格欄位寬度標準守衛)**：
   - 所有 `QTableWidget` 欄寬必須使用 `layout_constants.py` 常數定義，禁止元件內 hardcode magic numbers。
   - 關鍵業務欄位最小寬度標準：
     - 11 碼異常單號（`YYYYMMDDNNN`）：>= 120px
     - 13~15 碼產品料號（`XXXXXX-XXXXXX`）：>= 130px（主檔表格 150px）
     - 7 字 CJK 表頭（「品質異常單要求」）：>= 115px
     - 聯絡人 Email：>= 180px；電話：>= 140px
3. **Guard-Symmetric-Grid-Alignment (表單雙欄對稱與配對列鎖定守衛)**：
   - 密集表單採用標準雙欄對稱網格（`field_count=2`：直欄 0/2 為標籤，直欄 1/3 為輸入框，stretch 1:1），嚴禁在單一 Grid 中任意混排 2 欄/3 欄 offset。
   - `make_paired_form_row` 統一設定左標籤 76px 與右標籤 72px 基準最小寬度，保證不同字數標籤後方的輸入框垂直邊界完全對齊。

