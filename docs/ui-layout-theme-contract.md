# SQE DailyWork UI Layout and Theme Contract

### Global Display And System Preferences

- The `系統` sidebar group exposes the only global appearance and preferences entry: `顯示設定`. It routes to `PAGE_APPEARANCE_SETTINGS` in the main content stack, becomes the active sidebar page, and respects the current page's unsaved-form leave guard. Event-management pages must not create a duplicate appearance button or hidden compatibility widget.
- `AppearancePreferencesPage` provides a structured, finite 5-category settings surface with one vertical scroll owner per category:
  1. **外觀主題 (Appearance & Theme)**: page density (`緊湊` / `標準` / `舒適`), sidebar density (`緊湊` / `標準`), accent color (`科技藍 (Electric Blue)` / `深板岩海藍 (Slate Navy)` / `翡翠綠 (Emerald)` / `暖琥珀 (Amber)`), text size (`標準` / `放大`), and contrast mode (`標準` / `高對比`).
  2. **視覺表格與互動 (Visual, Tables & Interaction)**: table-reading density (`緊湊` / `標準` / `舒適`), alternating row colors, table grid lines, table page limit (`25` / `50` / `100` / `不分頁`), UI animations toggle, table row double-click action (`彈出操作選單` / `直接開啟檢視` / `直接開啟編輯`), search mode (`即時即打即找` / `按 Enter 或點搜尋`), default stats period span (`3 個月` / `6 個月` / `12 個月`), and Pareto 80/20 cutoff line toggle.
  3. **表單業務預設 (Form & Business Defaults)**: default responsible person, default anomaly category, default due days (`7 天` / `14 天` / `30 天`). Visit-create preference fields were removed in appearance preferences v10.
  4. **匯出與報告 (Export & Reports)**: default export directory, export completion action (`自動開啟匯出檔案` / `開啟所在資料夾` / `僅顯示通知`), report organization header, and export include charts toggle.
  5. **系統與備份 (System & Backup)**: default startup page (`events` / `defects` / `stats`; legacy `home` migrates to `events`), auto-backup prompt on exit, backup retention count (`5 份` / `10 份` / `20 份` / `30 份`), and delete confirmation prompt toggle.
- Preferences are local display and workflow default state stored under `ui_settings.appearance.preferences.v5`. Valid `v1`, `v2`, `v3`, and `v4` payloads map in memory to v5 defaults for added fields; `v5` is the active persistence key. Preferences must not alter workflow routes, SQE historical data, counts, statistics, exports, or NCR column-order compatibility keys.
- Appearance metrics are applied through shared QSS plus runtime sidebar/table helpers. Structural values in `layout_constants.py` remain authoritative and are not user-editable. High contrast is one fixed semantic palette for the whole desktop shell, popups, tables, and charts; it is not page-specific colour customization.
| Main workflow shell | `main.py` | `src/ui/main_window.py` / `MainWindow` | Desktop app | 1024 x 680 minimum, 1360 x 860 preferred, 95% active-screen cap | Page-specific layouts | `src/ui/theme.py`, `src/ui/layout_constants.py`, `src/ui/window_sizing.py` | `scripts/qt_visual_probe.py` |
| Supplier-event ops | Sidebar `作業佇列` | `src/ui/widgets/supplier_event_ops_page.py` / `SupplierEventOpsPage` | `MainWindow` | Fills content stack | Chips switch 逾期案件 / 根因待查 / 處置項目 / 案件總覽; chip `(N)` uses `get_supplier_event_queue_counts`; embedded queue/manager views; sidebar row has no badge | `CASE_QUEUE_*` / `OPERATIONAL_ACTION_QUEUE_COLUMNS` | `tests/test_supplier_event_queues.py` + native `scripts/qt_visual_probe.py --target main` |
| Event management (consolidated) | Sidebar `事件查詢` | `src/ui/widgets/defect_list_widget.py` / `EventListWidget` (`mode="query"`, no fixed scope) plus dedicated dialogs below | `MainWindow` | Fills content stack, dialogs clamped | Filter row with scope chips + table pagination; chips show per-scope counts; sidebar badge shows all open anomalies | Shared theme tokens | UI smoke |
| New anomaly | Sidebar `新增異常` | `src/ui/widgets/event_create_page.py` / `EventCreatePage`, with `NewAnomalyDialog` page presentation | `MainWindow` | Fills content stack | `CreateWorkflowShell` owns one scroll body and the bottom `返回清單` / `儲存` command row; saved page shows `查看清單` / `繼續新增` | Shared theme tokens | Focused page smoke + native `event-create` probe |
| Warehouse create | Sidebar `建立不合格品` | `src/ncr/embed.py` + `src/ncr/ui/defect_form.py` / embedded NCR create page | `MainWindow` | Fills content stack | `CreateWorkflowShell` owns the continuous-entry command row, feedback and one scroll body | Shared theme tokens plus `src/ncr/ui/ui_style.py` | Embedded smoke tests + native NCR visual probe |
| Warehouse pending outsource | Sidebar `待處理委外加工` | `src/ncr/embed.py` + `src/ncr/ui/defect_list.py` (`workflow="tracking"`, `processing_line="委外加工"`) | `MainWindow` / `NcrWorkflowPage` | Fills content stack; outer `PAGE_OUTER_MARGINS` come from `NcrWorkflowPage` only | `QueryWorkflowShell` + result `panel` are direct children of `DefectListWidget`; visible processing-line scope notice; no extra `create_page_shell` wrapper | Shared theme tokens plus `src/ncr/ui/ui_style.py` | Embedded smoke tests + native `ncr-tracker` probe |
| Warehouse pending material | Sidebar `待處理原物料` | `src/ncr/embed.py` + `src/ncr/ui/defect_list.py` (`workflow="tracking"`, `processing_line="原物料"`) | `MainWindow` / `NcrWorkflowPage` | Fills content stack; outer `PAGE_OUTER_MARGINS` come from `NcrWorkflowPage` only | Same flattened list topology as pending outsource | Shared theme tokens plus `src/ncr/ui/ui_style.py` | Embedded smoke tests + native `ncr-tracker` probe |
| Warehouse history | Sidebar `歷史紀錄` | `src/ncr/embed.py` + `src/ncr/ui/defect_list.py` (`workflow="trace"`) | `MainWindow` / `NcrWorkflowPage` | Fills content stack; outer `PAGE_OUTER_MARGINS` come from `NcrWorkflowPage` only | Same flattened list topology; closed/history table host | Shared theme tokens plus `src/ncr/ui/ui_style.py` | Embedded smoke tests + native `ncr-tracker` probe |
| Statistics | Sidebar `異常事件統計` | `src/ui/widgets/stats_view_widget.py` / `StatsViewWidget` | `MainWindow` | Fills content stack | Zero-noise supplier-event dashboard with date range, refresh, export, and trend / responsibility / supplier-risk chart panels; warehouse stats live only on 不合格品統計分析 | Shared theme tokens | UI smoke plus native dense-chart probe |
| Shared master lists | Sidebar 四主檔頁（原物料供應商 / 委外加工 / 原物料 / 半成品/成品） | `src/ui/widgets/master_data_widget.py` (`MasterDataSupplierPage` / `MasterDataProductPage`) | `MainWindow` | Fills content stack | Fixed-scope tables (no tab split) | Shared theme tokens | UI smoke |
| Supplier overview | Sidebar `供應商總覽` | `src/ui/widgets/supplier_overview_page.py` / `SupplierOverviewPage` | `MainWindow` | Fills content stack | Anomaly-focused read-only table; defaults to suppliers with open anomalies and shows latest anomaly number/date/category/problem summary/due date beside open and overdue counts; page filter supports open anomalies / any anomaly history / all active suppliers; entering the page refreshes from SQLite; double-click opens supplier 360 | Shared theme tokens plus `src/ui/layout_constants.py` | UI smoke |
| Supplier 360 | Supplier overview row | `src/ui/widgets/supplier_360_page.py` / `Supplier360Page` | `MainWindow` | Fills content stack | Source-labelled read-only timeline and separate anomaly / NCR tabs; legacy visit data is not exposed in product UI | Shared theme tokens | UI smoke plus native probe |
| Edit / preview anomaly | Event action menu | `src/ui/widgets/new_anomaly_dialog.py` / `NewAnomalyDialog` | Event list | Dialog helper clamps to active screen | One resizable scroll body with 基本資訊 / 問題描述 / 現場照片 sections and fixed footer; no tab host | Shared theme tokens | Focused dialog smoke plus native `form-density` probe |
| Close anomaly | Event action menu | `src/ui/widgets/close_anomaly_dialog.py` / `CloseAnomalyDialog` | Event list | Dialog helper clamps to active screen | Tab body with fixed footer | Shared theme tokens | Focused dialog smoke |
| Anomaly management page | Event action menu `案件詳情` / `編輯異常` | `src/ui/widgets/anomaly_management_page.py` / `AnomalyManagementPage` | MainWindow stack, opened from EventListWidget | Main content page, one scroll owner per tab; `案件詳情` is the read-only entry and `編輯異常` enters the same page's edit mode | Seven existing management areas plus header/stepper and `RepeatIssuesPanel`（潛在重複異常，無相似案件時顯示「無相似案件」）between stepper and tabs. The 改善措施 area renders every canonical Action with type, execution status, derived verification status, owner and due date; buttons expose only valid start / complete / cancel / verify transitions. Basic anomaly editing embeds `NewAnomalyDialog(embedded=True, page_mode=True)` | Shared theme tokens | `tests/test_anomaly_management_page.py`, `tests/test_repeat_issue_phase5.py`, `tests/test_case_actions_phase1.py`, native `scripts/qt_visual_probe.py --target workbench` at 1.0 / 1.25 / 1.5 |
| Anomaly workbench Action dialogs | Management page Action flows | `src/ui/widgets/anomaly_action_dialog.py` / `complete_action_dialog.py` / `add_verification_dialog.py` / `anomaly_root_cause_dialog.py` / `anomaly_hypothesis_dialog.py` | Anomaly management page | Dialog helper clamps to active screen; one scroll owner and fixed bottom command row | Create captures type, description, owner, due date and eligible verification-required choice. Root Cause dialog edits the single `anomaly_root_causes` row with status-conditioned validation. Completion and cancellation remain separate outcomes with completion evidence/note or mandatory cancellation reason. Verification is available only after execution completion. Required-field validation, dirty guard, CJK labels and audit-bundled writes remain mandatory | Shared theme tokens and layout constants | `tests/test_anomaly_workbench_dialogs.py`, `tests/test_anomaly_workbench_write_dialogs.py`, native `scripts/qt_visual_probe.py --target dialog-density` at 1.0 / 1.25 / 1.5 |
| Supplier and product dialogs | Master list actions | `src/ui/widgets/master_data_widget.py` dialogs | Master list | Dialog helper clamps to active screen | Tables/forms inside dialog content | Shared theme tokens | Focused dialog smoke |

## Screen-Fit Rules

- Use `fit_widget_to_available_screen` for top-level windows and `fit_dialog_to_available_screen` for dialogs.
- Keep the main window default near 1360 x 860, but cap first open to the active monitor work area.
- Keep the main workflow usable at 1024 x 680 or larger.
- Dialogs may shrink their minimum size to stay on screen; their primary buttons must remain outside scrollable content.
- Offscreen Qt checks are structural only. Use the native Windows visual probe before making visual fit or CJK-rendering claims.
- Treat visual issues as a primary acceptance item for UI changes, not a follow-up polish pass. Layout work must explicitly check long CJK text, dense chart/table content, button visibility, scroll boundaries, and 1024 x 680 fit because these areas frequently need second-pass correction.
- Visible overflow affordances are required on dense desktop pages. Do not hide
  scrollbars to create a cleaner static screenshot when the page can contain
  dense tables, charts, or long Chinese labels.
- `AppearancePreferencesPage` is a finite full-page settings surface across 5 domain categories: `外觀主題`,
  `視覺表格與互動`, `表單業務預設`, `匯出與報告`, and `系統與備份`, with fixed action buttons
  (`儲存並套用` / `放棄變更` / `還原預設`). Saving remains on the page with inline feedback;
  discarding restores the last persisted preview. Keep all preference controls, preview behavior,
  accessible descriptions, minimum-width reflow, and leave-guard restoration intact.
- All list surfaces follow the left-to-right reading chain
 `單號／日期 → 供應商 → 料號 → 品名 → 階段 → 異常類別／類別 → 責任人 → 摘要／描述 → 期限／處置 → 狀態`.
 `異常類別` and NCR `類別` must not be the last column and must remain visible in
 the default focused view. The canonical display definitions are owned by
 `src/ui/list_column_contract.py`.
- Supplier-event and NCR lists use responsive `重點欄位` mode at constrained
 widths. The event core is 異常單號／供應商／料號／品名／異常類別／問題摘要／品質異常單要求／狀態;
 the NCR core is 不良單號／發生日期／料號／產品名稱／類別／不良描述／狀態, with 處理線 also
  visible outside fixed processing-line pages. `完整欄位` restores every source
  column and may need horizontal scrolling. The mode is display-only and must
  not change exports, database records, or saved NCR column order.
- Color hierarchy is part of visual acceptance. Sidebars/navigation rails must
  review base surface, panel/footer surface, group labels, hover state, selected
  state, selected indicator, badges/status counts, primary action, secondary
  action, and brand/status accent colors. Avoid one-note dark or single-hue
  sidebars unless a documented brand constraint is compensated by contrast,
  borders, spacing, weight, and state indicators.

## Form Density Rules

## Shared Workflow Shell Rules

- `CreateWorkflowShell` is the only full-page create contract. It owns one
  vertical scroll body and a bottom command panel (Bottom Action Bar - 方案 A).
  The bottom command panel places secondary/reset actions on the left (`清除 / 重置`)
  and primary workflow actions on the right (`返回清單` + `儲存`), matching the
  top-to-bottom user input journey.
- `Dynamic Item List (BulletListWidget)`: Structured itemized entries (e.g. defect
  descriptions, action items, tracking points) must use the dynamic numbered row
  component (`BulletListWidget`) to support item-by-item review and dynamic addition
  (`+ 新增條目`), maintaining `\n` line-separated compatibility.
- `TagInputWidget`: Multi-select SMT process keyword chips with editable preset
  suggestions. Used on `NewAnomalyDialog` above the problem-description block;
  presets are maintained through `ProcessKeywordPresetsDialog` from
  `AppearancePreferencesPage` category 3.
- `AnalyticsWorkflowShell` & `Zero-Noise Analytics`: Standardizes the visible control
  surface for both statistics pages. Keeps only `篩選區間`, `重新整理` (variant="secondary"),
  `匯出 Excel` (variant="primary"), and visual chart panels. Verbose auto-generated
  text paragraphs and insight banners are removed from the visible layout to eliminate noise.
- `Form Iconography`: Section titles and key category groups use clean semantic
  emojis/icons (📋 基本/基礎資訊, 🔍 不良現象/問題描述, 📝 活動摘要, 📊 風險與統計, 📌 待追蹤事項)
  to enhance visual recognizability and form scanning efficiency.
- Modal edit and preview forms do not use `CreateWorkflowShell`: they retain a
  fixed `QDialogButtonBox` footer with 儲存／確認 left and 取消 right.

- Use side-by-side fields only for low-risk field groups where labels are short, fields have similar width needs, and the relationship is operationally obvious.
- Current good-only paired groups:
  - `ProductSectionEditor`: `時段 + 工單`.
  - `CloseAnomalyDialog`: single-row `結案日期` date picker plus `原因分類`;
    the retired `結案人員` field must not be displayed.
  - `SupplierFormDialog`: `主聯絡人 + 部門` and `電話/行動 + 電子郵件`.
  - `ProductFormDialog`: `料號 + 階段`.
- Keep large text, attachment, table, and long-selection fields as single-row blocks unless a later visual probe proves the paired version stays readable.
- Multi-line narrative fields use `BulletListWidget` (`[序號] [輸入框] [刪除]` + `+ 新增條目`); height grows with item count instead of fixed QTextEdit row caps.
- `NewAnomalyDialog` has two presentation modes. Edit/preview uses the dialog
  form with `AnomalyFormScroll` and a fixed footer; full-page create exposes the
  same fields through `CreateWorkflowShell` without a nested scroll area. The
  「品質異常單要求」是／否 radios are paired in 基本資訊 and begin unselected
  for new or legacy-unclassified records. The dialog prefers a 900 x 780
  working size, remains capped to the active screen and `FORM_MAX_WIDTH`, opens
  at the top of the form, and uses a compact scrollable attachment preview so
  an empty photo area does not consume the visible workflow.
- Deferred conditional candidates: `主要產品 + 料號`, `主供應商 + 次要供應商`, and other long combo-box rows. These require long supplier/product-name checks before implementation.
- Verify form density changes with focused structural tests plus `scripts/qt_visual_probe.py --target form-density` before treating CJK rendering and button visibility as confirmed.

### Manager View Shared Filter Semantics

- The shared「責任人」filter maps to **different fields per tab**: overview tab matches `anomalies.responsible_person` plus the current open action owner; queue tab matches `case_actions.owner` only.
- Placeholder and tooltip on the shared control must state this difference; when any filter is active, global KPI/metrics labels must note「指標為全域」.
- Regression: `tests/test_manager_view_phase6.py::test_owner_filter_matches_action_owner_in_summary_and_queue`; native `scripts/qt_visual_probe.py --target manager-view`.

## Theme Rules

- Keep colors, radius, typography, and control sizing in shared modules instead of page-local styles.
- **Chart Typography Hierarchy Contract**: All charts across `StatsViewWidget` (anomaly events) and `NcrStatsWidget` (warehouse nonconforming products) must consume the centralized font scale and helpers in `src/ui/widgets/chart_style.py`:
  - Chart Title: `11pt Bold` (`CHART_TITLE_POINT_SIZE`)
  - Axis Title: `9pt Bold` (`CHART_AXIS_TITLE_POINT_SIZE`)
  - Axis Labels (categories & tick values): `9pt Regular` (`CHART_AXIS_LABEL_POINT_SIZE`)
  - Legend Labels: `8pt Regular` (`CHART_LEGEND_POINT_SIZE`)
  - Data / Series / Point / Slice Labels: `8pt Regular / Bold` (`CHART_DATA_LABEL_POINT_SIZE`)
  Both modules inherit the active CJK font family chain and shared semantic tokens (`text_primary`, `chart_axis_text`, `chart_plot_bg`). Ad-hoc QFont sizing in individual chart builders is forbidden.
- Calendar popup QSS defines the light grid and explicit normal/disabled date
  text colors. `apply_app_theme` also installs the shared native-calendar
  palette guard because Windows ignores the QSS background for the internal
  `QTableView` Base role; both layers prevent dark dates on a dark grid.
- Combo-box popup lists follow the same two-layer contract: shared
  `QComboBox QAbstractItemView` QSS defines normal, selected, and disabled
  colors, while `apply_app_theme` installs an opaque native popup palette guard.
  Every combo in supplier-event, master-data, statistics, pagination, and NCR
  workflows inherits this contract; page-local popup colors are forbidden.
- Keep desktop pages dense and scan-friendly: direct labels, stable table sizing, visible action rows, and no nested page-wrapper cards.
- Do not change workflow order, data contracts, object names, or signal behavior for layout-only work.
- Supplier event pages and warehouse nonconforming-product pages must stay visually
  connected through the shell while keeping their data sources and statistics
  labeled separately.
- Default startup opens **事件查詢** (`default_startup_page=events`). Stack index `0`
  is a retired ghost placeholder; the home hub and `HomeWidget` are not product
  navigation. Do not reintroduce hero/cover panels, KPI cards, feature-tour blocks,
  or card-in-card wrappers for a decorative landing page.
- The consolidated **作業佇列** page (`SupplierEventOpsPage`) hosts four chips:
  逾期案件 / 根因待查 / 處置項目 / 案件總覽. Chip `(N)` labels use
  `get_supplier_event_queue_counts` (COUNT=LIST); the 案件總覽 chip has no count.
  Legacy PAGE_KEY aliases route to the same stack index and force the matching chip.
  Embedded queue pages omit standalone scope banners; workbench return from an ops
  chip shows `返回作業佇列`.
- Supplier event lists on the 事件查詢 page use scope chips (單獨異常 / 已結案)
  without a toolbar source tag. Statistics and NCR list pages retain their own
  compact source tags (`供應商事件`, `倉庫不合格品`). PDF export remains
  single-record output and is disabled until a row is selected. The table includes
  「品質異常單要求」 between 「缺失紀錄」 and 「狀態」; anomaly rows show 是／否／未設定
  from `anomalies.quality_report_required`. Anomaly rows expose `結案日期` from
  `anomalies.closed_at`. Visit product UI (scopes, preview dialog, create entry)
  is retired; legacy `visits` data remains in SQLite only.
- Warehouse nonconforming-product tracking exposes four first-class sidebar
  rows: 建立不合格品, 待處理委外加工, 待處理原物料, and 歷史紀錄. Do not
  reintroduce the retired outer `DefectTrackerPage` tab host for these
  entrypoints. Pending pages must be backed by visible `processing_line` scope,
  not by hidden filters or inferred category/return-slip values. List pages
  follow the event-query topology: `QueryWorkflowShell` and the result `panel`
  are direct children of `DefectListWidget`. `NcrWorkflowPage` already applies
  `PAGE_OUTER_MARGINS`; do not wrap the list in a second page-shell or content
  widget.
- Sidebar information architecture is workflow-first with four domain group
  headers (text labels): 供應商事件, 倉庫不合格品, 資料庫設定, 系統. 供應商事件提供
  `新增異常` / `事件查詢` / `作業佇列` / `異常事件統計`; 事件查詢頁內以
  `EVENT_QUERY_SCOPE_TABS` 對應的 scope chips 切換 單獨異常 / 已結案，已結案 chip
  鎖定狀態為 已結案。作業佇列頁內 chips 切換
  逾期案件 / 根因待查 / 處置項目 / 案件總覽。倉庫不合格品 holds
  建立不合格品 / 待處理委外加工 / 待處理原物料 / 歷史紀錄 / 不合格品統計分析;
  資料庫設定 holds 供應商總覽與四主檔頁（並排：原物料供應商 / 委外加工；原物料 / 半成品/成品；兩組以 pill 標籤底色區分供應商主檔與料號主檔）; 系統 holds 顯示設定。程式化 scope
  action 僅保留相容用途。Stack page indexes are
  (`0` 退休首頁佔位 / `1` 事件查詢 / `2` 異常事件統計 / `3` 建立不合格品 /
  `4` 待處理委外加工 / `5` 待處理原物料 / `6` 歷史紀錄 / `7` 不合格品統計分析 /
  `8` 原物料供應商 / `9` 委外加工 / `10` 原物料 / `11` 半成品/成品 / `12` 新增異常 / `13` 異常案件管理 / `14` 供應商總覽 /
  `15` 供應商檔案 / `16` 作業佇列 / `17` 顯示設定`, NCR offset 3). 導覽項目高度為 38px，群組間距為 10px；
  數值均由 `layout_constants.py` 管理。
- The sidebar is decoupled from stack indexes: it emits `nav_activated(action)`
  where action is `("page", PAGE_KEY)` or `("scope", EVENT_SCOPE_*)`; `MainWindow`
  maps PAGE_KEY → stack index and routes scope rows through
  `open_event_query_with_filters` / `EventListWidget.set_event_scope`. When page
  indexes or the PAGE_KEY map change, update the index constants, legacy aliases
  (`EVENT_CREATE_ANOMALY_PAGE_INDEX`), `ncr.embed.NCR_PAGE_OFFSET`,
  `_PAGE_KEY_TO_INDEX`, and the affected tests together (Atomic Path).
- Sidebar badges must expose pending work symmetrically: the supplier-event badge
  rides the 事件查詢 page row (all open supplier anomalies), while the event page
  chips expose scope-specific counts. Warehouse badges ride
  `待處理委外加工` / `待處理原物料` with count queries constrained to
  `status <> '已結案' AND processing_line = <formal line>`. `未分流` records are
  cleanup warnings/to-dos and must not be merged into either formal badge.
- Quick-create has no sidebar footer. 供應商事件的新增入口是側欄 `新增異常`
  全頁；倉庫不合格品維持 `建立不合格品` 側欄列。事件查詢工具列不得恢復冗餘
  `新增異常` 或 visit-create 按鈕。Do not reintroduce a global quick-create footer
  or a dedicated visit-create page.
- Statistics (異常事件統計) is supplier-event only: a dashboard-style page with
  one flat control row (`AnalyticsWorkflowShell`), one shared chart panel, and a
  2x2 four-phase chart grid. Zero-Noise: no insight strip, info banner, or
  verbose summary widgets (visible or hidden). Its visible source tag is compact;
  complete source, date-attribution, and scope guidance lives in the tag tooltip.
  The chart grid covers 供應商事件趨勢, 異常類別柏拉圖, 責任人事件統計, and
  SMT 製程關鍵字柏拉圖. The removed visit-trend phase, risk / overdue /
  not be recreated as visible or hidden page widgets. Warehouse nonconforming-product
  statistics live solely on the 不合格品統計分析 page (no duplicate warehouse tab here).
  Missing data displays `暫無資料`; no statistics table, cache, migration, or
  cross-workflow write path is allowed.
- Master-list update, disable, delete, and stage-log actions remain disabled
  until a row is selected, and the toolbar must name the current selected
  supplier or product before destructive actions become available. The master
  toolbar and real supplier/product tab host are direct page siblings; do not
  reintroduce an outer card solely to frame that single tool area.

## Historical UI/UX Checkpoints

The following dated checkpoints are retained for audit history. Current
behavior is defined by the routing table and cross-reference above.

**Superseded (visit product line):** Visit product UI (`NewVisitDialog`, visit
scope chips, visit trend charts, home KPI visit cards) was retired on
2026-09-02 by
[`retire-visit-product-line`](exec-plans/completed/retire-visit-product-line.md).
Current authoritative behavior is the routing table and cross-reference above,
not the visit-related bullets below.

### UI/UX Check - 2026-06-03

- Entrypoint: one daily shell, root `main.py`, with sidebar groups for
  event management, query/history, shared master data, and warehouse physical
  nonconforming products.
- Home topology: at this checkpoint, `HomeKpiPanel` was the only home workbench
  panel and contained exactly six KPI management cards. `HomeQuickActionPanel`,
  `OverdueBanner`,
  `HomeScrollArea`, `InfoPanel`, hero/banner widgets, and recent-event table
  attributes are retired.
- Container decision: keep functional panels for KPI, tables,
  filters, tab bodies, and dialogs; no decorative cover wrapper or page
  card-in-card shell remains in the first screen.
- NCR topology: one embedded `src/ncr/` workflow with three first-class shell
  pages (建立不合格品 / 待處理不合格品 / 歷史紀錄). Legacy standalone `defect.db`
  launch and the outer `DefectTrackerPage` tab host are retired.
- Form density check - 2026-06-04: supplier-event long text fields are compacted
  by visible row count; warehouse nonconforming-product description is full
  width; quick product creation uses a direct form instead of a decorative card;
  edit dialogs keep record context plus fixed bottom actions.
- Visit form fit (superseded) - 2026-07-14: the fixed-field visit dialog rendered its form
  directly without a whole-form `QScrollArea`; the activity summary used one
  visible row and the five tech-transfer checks shared one row. Retired with visit
  product UI; verify anomaly/workbench/dialog-density probes instead.
- Anomaly form horizontal fit - 2026-07-14: long supplier, product, and category
  values may elide inside their controls but must not expand the form beyond the
  visible viewport. The left descriptive column receives more stretch than the
  compact right metadata column; the horizontal scrollbar range must remain zero.
- UI/UX workbench check - 2026-06-05: verify clickable home KPI routing,
  disabled event PDF export before row selection, context-aware warehouse
  shortcut buttons, decision-summary routing/fallback, and master-data action
  disabled state with focused UI tests. Confirm native fit with
  `scripts/qt_visual_probe.py --target main` and
  `scripts/qt_visual_probe.py --target form-density`.
- Visual stress check - 2026-06-06: statistics pages keep functional scroll
  guards, full long names in tooltips, and no transparent warehouse chart
  wrapper. Confirm dense chart visual fit with
  `scripts/qt_visual_probe.py --target stats-stress`.
- Sidebar color review - 2026-06-06: sidebars must expose distinct role colors
  for rail base, logo/footer panel, group labels, active item, active indicator,
  badges, primary quick action, and secondary warehouse quick action.
- UI IA consolidation + daily cockpit (superseded visit scopes) - 2026-06-07: the three event sidebar
  entries (異常一覽表 / 訪廠紀錄一覽表 / 異常已結案查詢) were consolidated into one
  `事件查詢` page whose scope tabs were 單獨異常 / 訪廠發現異常 / 訪廠紀錄 / 已結案
  (default 單獨異常; the 已結案 tab locked the status filter to 已結案). Current
  product scopes are 單獨異常 / 已結案 only. Sidebar was
  now five items, page indexes rerun to `0/1/2/3/4` with NCR offset 4, and legacy
  index aliases are kept. Home gains one read-only backlog (待辦) list below the
  then-six KPI cards (open/overdue anomalies, overdue first, plus a warehouse
  pending shortcut) that only reads existing services and routes through existing
  navigation. `open_event_query_with_filters` now routes every scope through the
  single page (this fixes the former 訪廠發現異常 KPI scope mismatch and removes
  the orphan `visit_anomaly_widget`). Confirm with
  `scripts/qt_visual_probe.py --target main`.
- Visual-QA coverage + font/chart contract - 2026-06-22: the native probe gained
  list/empty/export targets (`event-list`, `master-data`, `ncr-tracker`,
  `empty-states`, `pdf-export`) plus `--scale` (multi-DPI), `--min-width`, a
  three-source CJK font report (`cjk_font_ok` / `ncr_cjk_font_ok` /
  `pdf_cjk_font_ok`), and a `qss_unknown_property_warnings` count. Live Qt QSS now
  uses only `font-weight` 400/700 (no 500/600); the CJK font fallback chain is a
  single source of truth in `src/ui/theme.py` (`ncr.ui.ui_style` imports it).
  Charts set figure vs plot-area backgrounds as separate tokens via
  `src/ui/widgets/chart_style.py` (`chart_plot_bg`). Visual regression baselines
  live in `tests/visual_baseline/` (`scripts/qt_visual_regress.py`). Pinned by
  `tests/test_font_source_single_truth.py` and
  `tests/test_theme_typography_consistency.py`.

## UI IA simplification (sidebar-first) - 2026-06-30

- Home KPIs reduced 6 → 4 (superseded visit KPI) - 2026-06-30: cards were
  `逾期未結 / 單獨異常 / 訪廠發現異常 / 倉庫待處理不合格品`; home hub is now retired.
  Also removed `總異常件數` and `已結案` cards (navigation later survived via the 單獨異常
  card and the 已結案 scope chip).
- Statistics de-duplicated: warehouse statistics were removed from
  異常事件統計, and visible supplier-event page tabs / decision-summary cards are
  no longer part of that page. Warehouse stats remain only on 不合格品統計分析.
  Dead warehouse chart code was removed from `stats_chart_mixin.py` and the
  `EventQueryScopeTabs` QSS retired.
- Sidebar footer quick-create (`＋新增異常` / `＋建立不合格品`) removed; creation uses
  in-page entries. The dead 72px placeholder gap was removed and three domain group
  headers added (供應商事件 / 倉庫不合格品 / 系統).
- Event scope tabs promoted to first-class sidebar rows (superseded) - 2026-06-30:
  rows were 單獨異常 / 訪廠發現異常 / 訪廠紀錄 / 已結案; current scopes live as
  in-page chips (單獨異常 / 已結案) on 事件查詢. The sidebar now emits
  `nav_activated(action)` (`("page", KEY)` | `("scope", SCOPE)`) instead of
  `page_changed(int)`; `MainWindow` owns the `_PAGE_KEY_TO_INDEX` map and
  `EventListWidget.set_event_scope` preserves supplier/month filters across scope
  switches.
- Warehouse workflow tabs were promoted to first-class sidebar rows on
  2026-07-01. The later 2026-07-04 dual-entry split is authoritative: indexes
  3/4/5/6 are 建立不合格品 / 待處理委外加工 / 待處理原物料 / 歷史紀錄,
  followed by 不合格品統計分析 at 7 and 基礎資料 at 8.
- Supplier statistics UI cleanup - 2026-07-01: `異常事件統計` follows the
  `不合格品統計分析` dashboard pattern: no visible page tabs, no visible
  risk/overdue/latest summary cards, one shared explanation banner, flattened
  chart grid container, and supplier-risk timing rendered as discrete points
  instead of a cross-supplier trend line.
- Supplier statistics four-phase Pareto update (superseded visit trend) - 2026-07-02: `異常事件統計`
  used the same chart topology as `不合格品統計分析`: one chart panel containing
  a 2x2 grid. The four cells were event trend, visit/anomaly trend,
  root-cause/Pareto category, and responsible-person load. Current grid has no
  visit-trend phase; see routing table above.
- Qt layout cleanup - 2026-07-01: `異常事件統計` no longer keeps hidden
  `StatsTabs` / chart-scroll proxy widgets after the visible dashboard grid
  became the source of truth. Warehouse `待處理不合格品` and `歷史紀錄`
  pages render their single result table directly instead of wrapping one table
  in a hidden `QTabWidget`; only the legacy `combined` warehouse list mode keeps
  a real two-tab table host.
- Shared UI helper cleanup - 2026-07-01: supplier-event statistics and
  warehouse statistics share `src/ui/widgets/stats_dashboard_helpers.py` for
  period controls, hidden compatibility month controls, scroll/grid scaffolding,
  info banners, and insight labels. Their data sources, chart builders, and
  export services remain separate. Event create/close dialogs (`NewAnomalyDialog`,
  `CloseAnomalyDialog`) use the
  shared dirty-tracking contract; NCR status badges use shared status tones.
  Retired standalone NCR tab selectors such as `workflowTabs`, `analysisTabs`,
  `homeSubTabs`, and `trackingOverviewTabs` should stay out of live QSS unless
  a real visible tab host is reintroduced with tests.
- Chart sizeHint stability check - 2026-07-02: To prevent QGraphicsView
  sizeHint height loops inside a widgetResizable QScrollArea (where resizing
  stretches the scene and feedback increases sizeHint), charts must use
  StableChartView instead of QChartView to ensure height stability on refresh.
- Verify with `scripts/qt_visual_probe.py --target main` and `--target stats-stress`,
  plus `tests/test_top_nav_compact_height`, `tests/test_ncr_embedding_smoke`,
  `tests/test_closed_tab_categories`, `tests/test_event_list_widget_render_stability`,
  `tests/test_stats_view_anomaly_chart`,
  and `tests/test_stats_refresh_height_stability`.
- Warehouse pending dual-entry update - 2026-07-04: Home removed the visible
  `HomeKpiPanel` / KPI cards and now keeps one backlog panel with three warehouse
  shortcuts (`待處理委外加工`, `待處理原物料`, `未分流待整理`). The sidebar replaces
  the retired generic `待處理不合格品` row with two formal pending rows backed by
  `defect_records.processing_line`; `未分流` is only a migrated cleanup state.
  NCR stack indexes are now `3 建立不合格品 / 4 待處理委外加工 / 5 待處理原物料 /
  6 歷史紀錄`, while `不合格品統計分析` is index 7 and `基礎資料` is index 8.
- Supplier-event operational queues - 2026-08-31: Sidebar exposes one consolidated
  **作業佇列** row; overdue / root-cause / open-actions / manager-summary chips live
  on `SupplierEventOpsPage`. Manager view exports only `案件總覽`. Home hub and
  `HomeWidget` are retired; confirm with `scripts/qt_visual_probe.py --target main`,
  `--target event-list`, and `--target manager-view` (ops chip for 案件總覽).

## Design Framework Cross-Reference (SQE Incident Management UI Design Framework v0.1 §7.7 items 1-9)

This contract is the **single source of truth for SQE DailyWork**; the design
framework document `docs/SQE_Incident_Management_UI_Design_Framework_v0.1.md`
chapter 7 section 7 ("DailyWork 整合映射") lists 15 "borrow from Web" candidate
advantages. Items 1-10 are implemented in this project through the shared
helpers and responsive column profiles below. Items 11-15 are documented for
future planning only and do not require new work in the current cycle.

| # | Framework advantage | SQE DailyWork authoritative location | Pinned by |
| - | --- | --- | --- |
| 1 | Semantic design tokens (no raw hex) | `src/ui/theme_tokens.py` (`TOKENS`, `TYPOGRAPHY`); palette source `src/ui/design_tokens.py` | `tests/test_theme_typography_consistency.py`, `tests/test_theme_minimal_surfaces.py` |
| 2 | CJK font fallback chain single source of truth | `src/ui/theme_tokens.py` (`PREFERRED_CJK_FONT_FAMILIES`, `CJK_FONT_FAMILY_CSS`); reused by `src/ncr/ui/ui_style.py` | `tests/test_font_source_single_truth.py` |
| 3 | Three workflow shells (Query / Analytics / Create) | `src/ui/widgets/common_widgets.py` (`QueryWorkflowShell`, `AnalyticsWorkflowShell`, `CreateWorkflowShell`) | Shell usage pinned by `tests/test_ncr_embedding_smoke.py`, `tests/test_event_list_widget_render_stability.py`, manual coverage by `scripts/qt_visual_probe.py --target main` |
| 4 | CreateWorkflowShell bottom command row + scroll body, fixed footer absent | `src/ui/widgets/common_widgets.py` (`CreateWorkflowShell`); modal dialogs retain `QDialogButtonBox` footer | `tests/test_form_inline_validation_and_dirty.py`, `tests/test_event_list_widget_render_stability.py` |
| 5 | DirtyTrackingMixin unified unsaved-changes guard | `src/ui/widgets/common_widgets.py` (`DirtyTrackingMixin`); applied to `NewAnomalyDialog` / `CloseAnomalyDialog` / `SupplierFormDialog` / `ProductFormDialog` / `SupplierContactManagerDialog` / `AddAnomalyActionDialog` / `AnomalyNoteDialog` / `CompleteActionDialog` / `AddVerificationDialog` / `AddEightDReviewDialog` / `AddAuditLogDialog` | `tests/test_form_inline_validation_and_dirty.py`, `tests/test_anomaly_workbench_write_dialogs.py` |
| 6 | Required marker + field-level instant validation | `src/ui/widgets/common_widgets.py` (`RequiredFieldLabel`, `set_field_invalid`, `make_inline_error_label`, `repolish`); QSS `[invalid]` selector in `src/ui/theme.py` | `tests/test_form_inline_validation_and_dirty.py`, `tests/test_form_field_pairing_layout.py` |
| 7 | EmptyStateWidget four-state ready | `src/ui/widgets/common_widgets.py` (`EmptyStateWidget`); used by event list, NCR list, statistics pages | `tests/test_layout_constants.py` (`EMPTY_STATE_MARGINS`), `scripts/qt_visual_probe.py --target empty-states` |
| 8 | Layout constants single source (min / preferred / max contract) | `src/ui/layout_constants.py`; window sizing helpers in `src/ui/window_sizing.py` | `tests/test_layout_constants.py`, `tests/test_window_sizing.py` |
| 9 | Workflow-first sidebar + routing decoupling + badge symmetry | `src/ui/sidebar_nav.py` (`_NAV_GROUPS`, `nav_activated` signal); `src/ui/main_window.py` (`_PAGE_KEY_TO_INDEX`, `_on_nav_activated`, `_refresh_sidebar_badge`) | `tests/test_top_nav_compact_height.py`, `tests/test_supplier_event_queues.py`, `scripts/qt_visual_probe.py --target main` |

When updating any of the locations above, keep the pinned tests green and add a
new entry in the change-log at the top of this file (or in
`docs/harness/closed-loop-log.md` for behavioural changes). New shared UI
helpers should ship together with their focused tests before being adopted by
widget pages — the AGENTS.md single-source rule forbids divergent copies.
