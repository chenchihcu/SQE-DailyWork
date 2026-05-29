# SQETOOL UI Layout and Theme Contract

## Entrypoint Matrix

| Entrypoint | Open path | File / class | Parent | Sizing policy | Overflow / scroll | Theme source | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Main workflow shell | `main.py` | `ui/main_window.py` / `MainWindow` | Desktop app | 1024 x 680 minimum, 1360 x 860 preferred, 95% active-screen cap | Page-specific layouts | `ui/theme.py`, `ui/layout_constants.py`, `ui/window_sizing.py` | `scripts/qt_visual_probe.py` |
| Home | Main tab `首頁` | `ui/widgets/home_widget.py` / `HomeWidget` | `MainWindow` | Fills tab content | Direct simplified layout with flattened info row (no `InfoPanel` wrapper) | Shared theme tokens | UI smoke + native visual probe |
| Visit records | Main tab `訪廠紀錄` | `ui/widgets/defect_list_widget.py` / `EventListWidget` | `MainWindow` | Fills tab content | Table pagination | Shared theme tokens | UI smoke |
| Visit anomalies | Main tab `訪廠發現異常` | `ui/widgets/defect_list_widget.py` / `EventListWidget` | `MainWindow` | Fills tab content | Table pagination | Shared theme tokens | UI smoke |
| Standalone anomalies | Main tab `單獨異常` | `ui/widgets/defect_list_widget.py` / `EventListWidget` | `MainWindow` | Fills tab content | Table pagination | Shared theme tokens | UI smoke |
| Closed cases | Main tab `已結案` | `ui/widgets/defect_list_widget.py` / `EventListWidget` | `MainWindow` | Fills tab content | Table pagination | Shared theme tokens | UI smoke |
| Statistics | Main tab `統計分析` | `ui/widgets/stats_view_widget.py` / `StatsViewWidget` | `MainWindow` | Fills tab content | Chart panels size from shared constants | Shared theme tokens | UI smoke |
| Master lists | Main tab `基礎清單` | `ui/widgets/master_data_widget.py` / `MasterDataWidget` | `MainWindow` | Fills tab content | Tables inside tabs | Shared theme tokens | UI smoke |
| New / edit anomaly | Anomaly buttons | `ui/widgets/defect_form_widget.py` / `NewAnomalyDialog` | `MainWindow` | Dialog helper clamps to active screen | Tab body with fixed footer | Shared theme tokens | Focused dialog smoke |
| New / edit visit | Visit buttons and home quick actions | `ui/widgets/defect_form_widget.py` / `NewVisitDialog` | `MainWindow` | Dialog helper clamps to active screen | Tab body with fixed footer | Shared theme tokens | Focused dialog smoke |
| Close anomaly | Event action menu | `ui/widgets/defect_form_widget.py` / `CloseAnomalyDialog` | Event list | Dialog helper clamps to active screen | Tab body with fixed footer | Shared theme tokens | Focused dialog smoke |
| Visit detail | Event action menu | `ui/widgets/event_actions.py` / `VisitDetailDialog` | Event list | Dialog helper clamps to active screen | Scrollable body, fixed header/footer | Shared theme tokens | Focused dialog smoke |
| Supplier and product dialogs | Master list actions | `ui/widgets/master_data_widget.py` dialogs | Master list | Dialog helper clamps to active screen | Tables/forms inside dialog content | Shared theme tokens | Focused dialog smoke |

## Screen-Fit Rules

- Use `fit_widget_to_available_screen` for top-level windows and `fit_dialog_to_available_screen` for dialogs.
- Keep the main window default near 1360 x 860, but cap first open to the active monitor work area.
- Keep the main workflow usable at 1024 x 680 or larger.
- Dialogs may shrink their minimum size to stay on screen; their primary buttons must remain outside scrollable content.
- Offscreen Qt checks are structural only. Use the native Windows visual probe before making visual fit or CJK-rendering claims.

## Form Density Rules

- Use side-by-side fields only for low-risk field groups where labels are short, fields have similar width needs, and the relationship is operationally obvious.
- Current good-only paired groups:
  - `NewVisitDialog`: `日期 + 訪廠人員`, `時段 + 工單`, and `數量 + 已技轉`.
  - `ProductSectionEditor`: `時段 + 工單`.
  - `CloseAnomalyDialog`: `結案人員 + 原因分類`.
  - `SupplierFormDialog`: `主聯絡人 + 部門` and `電話/行動 + 電子郵件`.
  - `ProductFormDialog`: `料號 + 階段`.
- Keep large text, attachment, table, and long-selection fields as single-row blocks unless a later visual probe proves the paired version stays readable.
- Deferred conditional candidates: `主要產品 + 料號`, `主供應商 + 次要供應商`, and other long combo-box rows. These require long supplier/product-name checks before implementation.
- Verify form density changes with focused structural tests plus the native Windows visual probe before treating CJK rendering and button visibility as confirmed.

## Theme Rules

- Keep colors, radius, typography, and control sizing in shared modules instead of page-local styles.
- Keep desktop pages dense and scan-friendly: direct labels, stable table sizing, visible action rows, and no nested page-wrapper cards.
- Do not change workflow order, data contracts, object names, or signal behavior for layout-only work.
