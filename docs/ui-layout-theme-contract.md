# SQE DailyWork UI Layout and Theme Contract

## Entrypoint Matrix

| Entrypoint | Open path | File / class | Parent | Sizing policy | Overflow / scroll | Theme source | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Main workflow shell | `main.py` | `src/ui/main_window.py` / `MainWindow` | Desktop app | 1024 x 680 minimum, 1360 x 860 preferred, 95% active-screen cap | Page-specific layouts | `src/ui/theme.py`, `src/ui/layout_constants.py`, `src/ui/window_sizing.py` | `scripts/qt_visual_probe.py` |
| Home workbench | Sidebar `首頁` | `src/ui/widgets/home_widget.py` / `HomeWidget` | `MainWindow` | Fills content stack | Six KPI management cards plus a read-only backlog (待辦) list | Shared theme tokens | UI smoke + native visual probe |
| Event management (consolidated) | Sidebar `事件管理` | `src/ui/widgets/defect_list_widget.py` / `EventListWidget` (`mode="query"`, no fixed scope) plus `src/ui/widgets/defect_form_widget.py` dialogs | `MainWindow` | Fills content stack, dialogs clamped | Scope tabs (單獨異常 / 訪廠發現異常 / 訪廠紀錄 / 已結案) + table pagination + visit dialog body scroll | Shared theme tokens | UI smoke |
| Warehouse nonconforming tracker | Sidebar `不合格品追蹤` | `src/ncr/embed.py` / embedded NCR page | `MainWindow` | Fills content stack | Embedded tab/table layout | Shared theme tokens plus `src/ncr/ui/ui_style.py` | Embedded smoke tests |
| Statistics | Sidebar `異常事件統計` | `src/ui/widgets/stats_view_widget.py` / `StatsViewWidget` | `MainWindow` | Fills content stack | Functional tab-level scroll guards and chart panels sized from shared constants | Shared theme tokens | UI smoke plus native dense-chart probe |
| Shared master lists | Sidebar `基礎資料` | `src/ui/widgets/master_data_widget.py` / `MasterDataWidget` | `MainWindow` | Fills content stack | Tables inside tabs | Shared theme tokens | UI smoke |
| New / edit anomaly | Anomaly buttons | `src/ui/widgets/defect_form_widget.py` / `NewAnomalyDialog` | `MainWindow` | Dialog helper clamps to active screen | Tab body with fixed footer | Shared theme tokens | Focused dialog smoke |
| New / edit visit | Visit list actions and sidebar footer action | `src/ui/widgets/defect_form_widget.py` / `NewVisitDialog` | `MainWindow` | Dialog helper clamps to active screen | Tab body with fixed footer | Shared theme tokens | Focused dialog smoke |
| Close anomaly | Event action menu | `src/ui/widgets/defect_form_widget.py` / `CloseAnomalyDialog` | Event list | Dialog helper clamps to active screen | Tab body with fixed footer | Shared theme tokens | Focused dialog smoke |
| Visit detail | Event action menu | `src/ui/widgets/event_actions.py` / `VisitDetailDialog` | Event list | Dialog helper clamps to active screen | Scrollable body, fixed header/footer | Shared theme tokens | Focused dialog smoke |
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
- Color hierarchy is part of visual acceptance. Sidebars/navigation rails must
  review base surface, panel/footer surface, group labels, hover state, selected
  state, selected indicator, badges/status counts, primary action, secondary
  action, and brand/status accent colors. Avoid one-note dark or single-hue
  sidebars unless a documented brand constraint is compensated by contrast,
  borders, spacing, weight, and state indicators.

## Form Density Rules

- Use side-by-side fields only for low-risk field groups where labels are short, fields have similar width needs, and the relationship is operationally obvious.
- Current good-only paired groups:
  - `NewVisitDialog`: `日期 + 訪廠人員`, `時段 + 工單`, and `數量 + 已技轉`.
  - `ProductSectionEditor`: `時段 + 工單`.
  - `CloseAnomalyDialog`: `結案人員 + 原因分類`.
  - `SupplierFormDialog`: `主聯絡人 + 部門` and `電話/行動 + 電子郵件`.
  - `ProductFormDialog`: `料號 + 階段`.
- Keep large text, attachment, table, and long-selection fields as single-row blocks unless a later visual probe proves the paired version stays readable.
- Long text boxes use row-count-based initial heights instead of legacy large fixed heights; they remain single-column fields.
- Deferred conditional candidates: `主要產品 + 料號`, `主供應商 + 次要供應商`, and other long combo-box rows. These require long supplier/product-name checks before implementation.
- Verify form density changes with focused structural tests plus `scripts/qt_visual_probe.py --target form-density` before treating CJK rendering and button visibility as confirmed.

## Theme Rules

- Keep colors, radius, typography, and control sizing in shared modules instead of page-local styles.
- Keep desktop pages dense and scan-friendly: direct labels, stable table sizing, visible action rows, and no nested page-wrapper cards.
- Do not change workflow order, data contracts, object names, or signal behavior for layout-only work.
- Supplier event pages and warehouse nonconforming-product pages must stay visually
  connected through the shell while keeping their data sources and statistics
  labeled separately.
- Home is an operations workbench (daily cockpit): six KPI management cards
  followed by one read-only backlog (待辦) list. Still forbidden: quick-entry
  write panels, hero/cover banners, feature-tour blocks, and project-structure
  explanations. The backlog list is not a generic recent-event feed — it is a
  filtered, actionable to-do list (open / overdue anomalies) that only reads
  existing services and only routes through existing navigation.
- Home KPI cards and backlog rows are operational shortcuts. The six cards plus
  the single backlog list are the complete first-screen contract, and each must
  provide a hover/click affordance that routes through existing main-window
  navigation with filters instead of introducing new write paths. The backlog
  list reads existing services only (`event_service.list_events` plus the
  warehouse summary); it must not add statistics tables, caches, migrations, or
  cross-workflow write paths.
- Supplier event lists show a compact source tag such as `供應商事件 / 單獨異常`
  or `供應商事件 / 訪廠發現異常`. PDF export remains single-record output and
  is disabled until a row is selected.
- Warehouse nonconforming-product tracking uses one sidebar entry and internal
  tabs for 待處理、結案溯源、連續登錄; do not reintroduce multiple sidebar
  shell pages for the same warehouse workflow.
- Sidebar information architecture is workflow-first with one item per group:
  首頁 (overview), 事件管理 (supplier events), 異常事件統計 (analysis), 基礎資料
  (master data), and 不合格品追蹤 (warehouse). Groups are conveyed by per-item
  icons and spacing (no text section headers or divider lines). Page indexes:
  `0 首頁 / 1 事件管理 / 2 異常事件統計 / 3 基礎資料 / 4 不合格品追蹤` (NCR offset 4).
  The former 異常一覽表 / 訪廠紀錄一覽表 / 異常已結案查詢 entries are now scope
  tabs inside 事件管理. When page indexes change, update the index constants,
  legacy aliases (`ANOMALY/VISIT/CLOSED_PAGE_INDEX`), `ncr.embed.NCR_PAGE_OFFSET`,
  and the affected tests together (Atomic Path).
- Sidebar badges must expose pending work symmetrically for supplier events and
  warehouse physical nonconforming products.
- Sidebar quick-create actions live in a separate footer: supplier anomaly
  creation is the primary action, warehouse nonconforming-product creation is a
  secondary action.
- The warehouse page toolbar is context-aware: the internal `建立不合格品`
  tab stays present, while duplicate shortcut buttons hide when the current tab
  already represents the same action.
- Statistics may show a compact decision-summary strip above charts, but it
  must read only existing service data. Missing data displays `暫無資料`; no
  statistics table, cache, migration, or cross-workflow write path is allowed.
- Master-list update, disable, delete, and stage-log actions remain disabled
  until a row is selected, and the toolbar must name the current selected
  supplier or product before destructive actions become available.

## UI/UX Check - 2026-06-03

- Entrypoint: one daily shell, root `main.py`, with sidebar groups for
  event management, query/history, shared master data, and warehouse physical
  nonconforming products.
- Home topology: `HomeKpiPanel` is the only home workbench panel and contains
  exactly six KPI management cards. `HomeQuickActionPanel`, `OverdueBanner`,
  `HomeScrollArea`, `InfoPanel`, hero/banner widgets, and recent-event table
  attributes are retired.
- Container decision: keep functional panels for KPI, tables,
  filters, tab bodies, and dialogs; no decorative cover wrapper or page
  card-in-card shell remains in the first screen.
- NCR topology: one embedded `DefectTrackerPage` with internal tabs. Legacy
  standalone `defect.db` launch and multi-page NCR sidebar shell are retired.
- Form density check - 2026-06-04: supplier-event long text fields are compacted
  by visible row count; warehouse nonconforming-product description is full
  width; quick product creation uses a direct form instead of a decorative card;
  edit dialogs keep record context plus fixed bottom actions.
- UI/UX workbench check - 2026-06-05: verify clickable home KPI routing,
  disabled event PDF export before row selection, context-aware warehouse
  shortcut buttons, decision-summary routing/fallback, and master-data action
  disabled state with focused UI tests. Confirm native fit with
  `scripts/qt_visual_probe.py --target main` and
  `scripts/qt_visual_probe.py --target form-density`.
- Visual stress check - 2026-06-06: statistics pages keep functional tab-level
  scroll guards, compact 2 x 2 decision-summary buttons, full long names in
  tooltips, and no transparent warehouse chart wrapper. Confirm dense chart
  visual fit with `scripts/qt_visual_probe.py --target stats-stress`.
- Sidebar color review - 2026-06-06: sidebars must expose distinct role colors
  for rail base, logo/footer panel, group labels, active item, active indicator,
  badges, primary quick action, and secondary warehouse quick action.
- UI IA consolidation + daily cockpit - 2026-06-07: the three event sidebar
  entries (異常一覽表 / 訪廠紀錄一覽表 / 異常已結案查詢) are consolidated into one
  `事件管理` page whose scope tabs are 單獨異常 / 訪廠發現異常 / 訪廠紀錄 / 已結案
  (default 單獨異常; the 已結案 tab locks the status filter to 已結案). Sidebar is
  now five items, page indexes rerun to `0/1/2/3/4` with NCR offset 4, and legacy
  index aliases are kept. Home gains one read-only backlog (待辦) list below the
  six KPI cards (open/overdue anomalies, overdue first, plus a warehouse pending
  shortcut) that only reads existing services and routes through existing
  navigation. `open_event_query_with_filters` now routes every scope through the
  single page (this fixes the former 訪廠發現異常 KPI scope mismatch and removes
  the orphan `visit_anomaly_widget`). Confirm with
  `scripts/qt_visual_probe.py --target main`.
