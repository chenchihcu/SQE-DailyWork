# SQE DailyWork UI Layout and Theme Contract

## Entrypoint Matrix

| Entrypoint | Open path | File / class | Parent | Sizing policy | Overflow / scroll | Theme source | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Main workflow shell | `main.py` | `src/ui/main_window.py` / `MainWindow` | Desktop app | 1024 x 680 minimum, 1360 x 860 preferred, 95% active-screen cap | Page-specific layouts | `src/ui/theme.py`, `src/ui/layout_constants.py`, `src/ui/window_sizing.py` | `scripts/qt_visual_probe.py` |
| Home workbench | Sidebar `首頁` | `src/ui/widgets/home_widget.py` / `HomeWidget` | `MainWindow` | Fills content stack | Four KPI management cards plus a read-only backlog (待辦) list | Shared theme tokens | UI smoke + native visual probe |
| Event management (consolidated) | Sidebar 供應商事件 scope 列 (單獨異常 / 訪廠發現異常 / 訪廠紀錄 / 已結案) | `src/ui/widgets/defect_list_widget.py` / `EventListWidget` (`mode="query"`, no fixed scope) plus `src/ui/widgets/defect_form_widget.py` dialogs | `MainWindow` | Fills content stack, dialogs clamped | Filter row + table pagination + visit dialog body scroll; active scope shown via source tag (no in-page scope tab bar) | Shared theme tokens | UI smoke |
| Warehouse create | Sidebar `建立不合格品` | `src/ncr/embed.py` + `src/ncr/ui/defect_form.py` / embedded NCR create page | `MainWindow` | Fills content stack | Continuous-entry form layout | Shared theme tokens plus `src/ncr/ui/ui_style.py` | Embedded smoke tests + native NCR visual probe |
| Warehouse pending | Sidebar `待處理不合格品` | `src/ncr/embed.py` + `src/ncr/ui/defect_list.py` (`workflow="tracking"`) | `MainWindow` | Fills content stack | Pending table layout with functional internal table host | Shared theme tokens plus `src/ncr/ui/ui_style.py` | Embedded smoke tests + native NCR visual probe |
| Warehouse history | Sidebar `歷史紀錄` | `src/ncr/embed.py` + `src/ncr/ui/defect_list.py` (`workflow="trace"`) | `MainWindow` | Fills content stack | Closed/history table layout with functional internal table host | Shared theme tokens plus `src/ncr/ui/ui_style.py` | Embedded smoke tests + native NCR visual probe |
| Statistics | Sidebar `異常事件統計` | `src/ui/widgets/stats_view_widget.py` / `StatsViewWidget` | `MainWindow` | Fills content stack | Supplier-event dashboard with one control row, one explanation banner, trend / responsibility / supplier-risk chart panels, and scroll guards; warehouse stats live only on 不合格品統計分析 | Shared theme tokens | UI smoke plus native dense-chart probe |
| Shared master lists | Sidebar `基礎資料` | `src/ui/widgets/master_data_widget.py` / `MasterDataWidget` | `MainWindow` | Fills content stack | Tables inside tabs | Shared theme tokens | UI smoke |
| New / edit anomaly | Anomaly buttons | `src/ui/widgets/defect_form_widget.py` / `NewAnomalyDialog` | `MainWindow` | Dialog helper clamps to active screen | Tab body with fixed footer | Shared theme tokens | Focused dialog smoke |
| New / edit visit | Visit list actions and event toolbar `新增訪廠` | `src/ui/widgets/defect_form_widget.py` / `NewVisitDialog` | `MainWindow` | Dialog helper clamps to active screen | Tab body with fixed footer | Shared theme tokens | Focused dialog smoke |
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
- Home is an operations workbench (daily cockpit): four KPI management cards
  followed by one read-only backlog (待辦) list. Still forbidden: quick-entry
  write panels, hero/cover banners, feature-tour blocks, and project-structure
  explanations. The backlog list is not a generic recent-event feed — it is a
  filtered, actionable to-do list (open / overdue anomalies) that only reads
  existing services and only routes through existing navigation.
- Home KPI cards and backlog rows are operational shortcuts. The four cards plus
  the single backlog list are the complete first-screen contract, and each must
  provide a hover/click affordance that routes through existing main-window
  navigation with filters instead of introducing new write paths. The backlog
  list reads existing services only (`event_service.list_events` plus the
  warehouse summary); it must not add statistics tables, caches, migrations, or
  cross-workflow write paths.
- Supplier event lists show a compact source tag such as `供應商事件 / 單獨異常`
  or `供應商事件 / 訪廠發現異常`. PDF export remains single-record output and
  is disabled until a row is selected.
- Warehouse nonconforming-product tracking exposes three first-class sidebar
  rows: 建立不合格品, 待處理不合格品, and 歷史紀錄. Do not reintroduce the retired
  outer `DefectTrackerPage` tab host for these three entrypoints.
- Sidebar information architecture is workflow-first with three domain group
  headers (text labels): 供應商事件, 倉庫不合格品, 系統. The four supplier-event
  scopes are first-class nav rows (單獨異常 / 訪廠發現異常 / 訪廠紀錄 / 已結案,
  default 單獨異常; the 已結案 row locks the status filter to 已結案) plus 異常事件統計;
  倉庫不合格品 holds 建立不合格品 / 待處理不合格品 / 歷史紀錄 / 不合格品統計分析; 系統 holds 基礎資料. There is no
  in-page scope tab bar — the event page is driven by the active sidebar scope row,
  shown via the source tag. Stack page indexes are
  (`0 首頁 / 1 事件管理 / 2 異常事件統計 / 3 建立不合格品 / 4 待處理不合格品 /
  5 歷史紀錄 / 6 不合格品統計分析 / 7 基礎資料`, NCR offset 3).
- The sidebar is decoupled from stack indexes: it emits `nav_activated(action)`
  where action is `("page", PAGE_KEY)` or `("scope", EVENT_SCOPE_*)`; `MainWindow`
  maps PAGE_KEY → stack index and routes scope rows through
  `open_event_query_with_filters` / `EventListWidget.set_event_scope`. When page
  indexes or the PAGE_KEY map change, update the index constants, legacy aliases
  (`ANOMALY/VISIT/CLOSED_PAGE_INDEX`), `ncr.embed.NCR_PAGE_OFFSET`,
  `_PAGE_KEY_TO_INDEX`, and the affected tests together (Atomic Path).
- Sidebar badges must expose pending work symmetrically: the supplier-event badge
  rides the 單獨異常 scope row (open anomalies), the warehouse badge rides 待處理不合格品.
- Quick-create has no sidebar footer. Creation uses each page's existing entry
  points: the event toolbar `新增異常` / `新增訪廠`, and the 倉庫不合格品 sidebar
  `建立不合格品` row. Do not reintroduce a global quick-create footer.
- Statistics (異常事件統計) is supplier-event only: a dashboard-style page with
  one control row, one explanation banner, and chart panels for 趨勢 / 責任人績效 /
  供應商風險. The removed risk / overdue / latest decision-summary cards must not
  be recreated as visible or hidden page widgets. Warehouse nonconforming-product
  statistics live solely on the 不合格品統計分析 page (no duplicate warehouse tab
  here). Missing
  data displays `暫無資料`; no statistics table, cache, migration, or
  cross-workflow write path is allowed.
- Master-list update, disable, delete, and stage-log actions remain disabled
  until a row is selected, and the toolbar must name the current selected
  supplier or product before destructive actions become available.

## UI/UX Check - 2026-06-03

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
- UI IA consolidation + daily cockpit - 2026-06-07: the three event sidebar
  entries (異常一覽表 / 訪廠紀錄一覽表 / 異常已結案查詢) are consolidated into one
  `事件管理` page whose scope tabs are 單獨異常 / 訪廠發現異常 / 訪廠紀錄 / 已結案
  (default 單獨異常; the 已結案 tab locks the status filter to 已結案). Sidebar is
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

- Home KPIs reduced 6 → 4 (`逾期未結 / 單獨異常 / 訪廠發現異常 / 倉庫待處理不合格品`);
  removed `總異常件數` and `已結案` cards (their navigation survives via the 單獨異常
  card and the 已結案 sidebar scope row).
- Statistics de-duplicated: warehouse statistics were removed from
  異常事件統計, and visible supplier-event page tabs / decision-summary cards are
  no longer part of that page. Warehouse stats remain only on 不合格品統計分析.
  Dead warehouse chart code was removed from `stats_chart_mixin.py` and the
  `EventQueryScopeTabs` QSS retired.
- Sidebar footer quick-create (`＋新增異常` / `＋建立不合格品`) removed; creation uses
  in-page entries. The dead 72px placeholder gap was removed and three domain group
  headers added (供應商事件 / 倉庫不合格品 / 系統).
- Event scope tabs promoted to first-class sidebar rows (單獨異常 / 訪廠發現異常 /
  訪廠紀錄 / 已結案); the in-page scope tab bar was removed. The sidebar now emits
  `nav_activated(action)` (`("page", KEY)` | `("scope", SCOPE)`) instead of
  `page_changed(int)`; `MainWindow` owns the `_PAGE_KEY_TO_INDEX` map and
  `EventListWidget.set_event_scope` preserves supplier/month filters across scope
  switches.
- Warehouse workflow tabs promoted to first-class sidebar rows - 2026-07-01:
  `建立不合格品`, `待處理不合格品`, and `歷史紀錄` now occupy stack indexes 3/4/5;
  `不合格品統計分析` moves to index 6 and `基礎資料` to index 7. The warehouse
  pending badge rides `待處理不合格品`; `open_warehouse_nonconforming_tracker()`
  routes there, while `open_warehouse_nonconforming_create()` routes to
  `建立不合格品`.
- Supplier statistics UI cleanup - 2026-07-01: `異常事件統計` follows the
  `不合格品統計分析` dashboard pattern: no visible page tabs, no visible
  risk/overdue/latest summary cards, one shared explanation banner, flattened
  chart grid container, and supplier-risk timing rendered as discrete points
  instead of a cross-supplier trend line.
- Verify with `scripts/qt_visual_probe.py --target main` and `--target stats-stress`,
  plus `tests/test_top_nav_compact_height`, `tests/test_ncr_embedding_smoke`,
  `tests/test_closed_tab_categories`, `tests/test_event_list_widget_render_stability`,
  `tests/test_home_recent_events_panel`, and `tests/test_stats_view_anomaly_chart`.
