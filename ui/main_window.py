import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from services import event_service
from ui.layout_constants import (
    MAIN_WINDOW_DEFAULT_HEIGHT,
    MAIN_WINDOW_DEFAULT_WIDTH,
    MAIN_WINDOW_MAX_HEIGHT,
    MAIN_WINDOW_MAX_WIDTH,
    MAIN_WINDOW_MIN_HEIGHT,
    MAIN_WINDOW_MIN_WIDTH,
)
from ui.page_header_bar import PageHeaderBar
from ui.sidebar_nav import SidebarNav
from ui.theme import asset_path
from ui.window_sizing import fit_widget_to_available_screen
from ui.widgets.defect_form_widget import NewAnomalyDialog, NewVisitDialog
from ui.widgets.defect_list_widget import EventListWidget
from ui.widgets.home_widget import HomeWidget
from ui.widgets.master_data_widget import MasterDataWidget
from ui.widgets.stats_view_widget import StatsViewWidget

HOME_PAGE_INDEX = 0
ANOMALY_PAGE_INDEX = 1
VISIT_PAGE_INDEX = 2
STATS_PAGE_INDEX = 3
CLOSED_PAGE_INDEX = 4
MASTER_PAGE_INDEX = 5

# Legacy index aliases kept for external callers
VISIT_ANOMALY_PAGE_INDEX = ANOMALY_PAGE_INDEX
STANDALONE_ANOMALY_PAGE_INDEX = ANOMALY_PAGE_INDEX

_PAGE_TITLES = {
    HOME_PAGE_INDEX:    ("首頁",       "Mitcorp SQE Tool"),
    ANOMALY_PAGE_INDEX: ("異常管理",   "異常事件追蹤與改善閉環"),
    VISIT_PAGE_INDEX:   ("訪廠紀錄",   "廠商訪視與現場缺失記錄"),
    STATS_PAGE_INDEX:   ("統計分析",   "品質數據統計與趨勢分析"),
    CLOSED_PAGE_INDEX:  ("已結案紀錄", "歷史結案事件查詢"),
    MASTER_PAGE_INDEX:  ("基礎資料",   "供應商與品名主檔管理"),
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mitcorp 供應商品質管理系統")
        self.setWindowIcon(QIcon(str(asset_path("mitcorp_logo.png"))))
        fit_widget_to_available_screen(
            self,
            preferred_width=MAIN_WINDOW_DEFAULT_WIDTH,
            preferred_height=MAIN_WINDOW_DEFAULT_HEIGHT,
            minimum_width=MAIN_WINDOW_MIN_WIDTH,
            minimum_height=MAIN_WINDOW_MIN_HEIGHT,
            maximum_width=MAIN_WINDOW_MAX_WIDTH,
            maximum_height=MAIN_WINDOW_MAX_HEIGHT,
        )
        self._last_non_master_index = HOME_PAGE_INDEX
        self._setup_ui()
        self._refresh_sidebar_badge()

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("AppRoot")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 左側導覽側欄 ──────────────────────────────────
        self.sidebar = SidebarNav()
        self.sidebar.page_changed.connect(self._on_sidebar_page_changed)
        self.sidebar.quick_create_clicked.connect(self.open_new_anomaly_dialog)
        root.addWidget(self.sidebar)

        # ── 右側內容區 ────────────────────────────────────
        content_area = QFrame()
        content_area.setObjectName("ContentHost")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._header_bar = PageHeaderBar()
        content_layout.addWidget(self._header_bar)

        # 頁面堆疊
        self.stack = QStackedWidget()
        self.stack.setObjectName("PageStack")

        self.home_widget = HomeWidget(self)
        self.standalone_anomaly_widget = EventListWidget(
            self, mode="query", fixed_scope=event_service.EVENT_SCOPE_ANOMALY_ONLY
        )
        self.visit_widget = EventListWidget(
            self, mode="query", fixed_scope=event_service.EVENT_SCOPE_VISIT_ONLY
        )
        self.stats_widget = StatsViewWidget(self)
        self.closed_event_widget = EventListWidget(
            self,
            mode="query",
            fixed_scope=event_service.EVENT_SCOPE_CLOSED_ONLY,
            fixed_status="已結案",
        )
        self.master_widget = MasterDataWidget(self)

        # visit_anomaly_widget kept for compatibility with open_event_query_with_filters
        self.visit_anomaly_widget = EventListWidget(
            self, mode="query", fixed_scope=event_service.EVENT_SCOPE_VISIT_WITH_ANOMALY
        )

        self.stack.insertWidget(HOME_PAGE_INDEX,    self.home_widget)
        self.stack.insertWidget(ANOMALY_PAGE_INDEX, self.standalone_anomaly_widget)
        self.stack.insertWidget(VISIT_PAGE_INDEX,   self.visit_widget)
        self.stack.insertWidget(STATS_PAGE_INDEX,   self.stats_widget)
        self.stack.insertWidget(CLOSED_PAGE_INDEX,  self.closed_event_widget)
        self.stack.insertWidget(MASTER_PAGE_INDEX,  self.master_widget)

        # Compatibility aliases used by tests / older callers
        # events_widget points to the anomaly list at index 1 (primary event management page)
        self.events_widget = self.standalone_anomaly_widget
        self.entry_widget = self.visit_widget

        content_layout.addWidget(self.stack, 1)
        root.addWidget(content_area, 1)

        self._switch_primary_page(HOME_PAGE_INDEX)

    # ── Navigation ──────────────────────────────────────────────────────────

    def _switch_primary_page(self, page_index: int) -> None:
        count = self.stack.count()
        if page_index < 0 or page_index >= count:
            return
        self.stack.setCurrentIndex(page_index)
        self.sidebar.set_active(page_index)
        title, subtitle = _PAGE_TITLES.get(page_index, ("", ""))
        self._header_bar.set_page(title, subtitle)
        if page_index != MASTER_PAGE_INDEX:
            self._last_non_master_index = page_index

    def _on_sidebar_page_changed(self, index: int) -> None:
        if index == MASTER_PAGE_INDEX:
            self._open_master_data()
        else:
            self._switch_primary_page(index)

    def _open_master_data(self) -> None:
        self._switch_primary_page(MASTER_PAGE_INDEX)

    def return_from_master(self) -> None:
        target = self._last_non_master_index
        if target < 0 or target >= self.stack.count() or target == MASTER_PAGE_INDEX:
            target = HOME_PAGE_INDEX
        self._switch_primary_page(target)

    def open_event_query_with_filters(
        self,
        *,
        event_type: str = "ANOMALY",
        supplier_keyword: str = "",
        yyyymm: str | None = None,
        status: str = "ALL",
        event_scope: str | None = None,
    ) -> None:
        target_index = ANOMALY_PAGE_INDEX
        target_widget = self.standalone_anomaly_widget

        if event_scope == event_service.EVENT_SCOPE_CLOSED_ONLY:
            target_index = CLOSED_PAGE_INDEX
            target_widget = self.closed_event_widget
        elif event_scope == event_service.EVENT_SCOPE_VISIT_ONLY:
            target_index = VISIT_PAGE_INDEX
            target_widget = self.visit_widget
        elif event_scope in (
            event_service.EVENT_SCOPE_ANOMALY_ONLY,
            event_service.EVENT_SCOPE_VISIT_WITH_ANOMALY,
        ):
            target_index = ANOMALY_PAGE_INDEX
            target_widget = self.standalone_anomaly_widget
        else:
            if event_type == "VISIT":
                target_index = VISIT_PAGE_INDEX
                target_widget = self.visit_widget

        self._switch_primary_page(target_index)
        target_widget.apply_quick_filters(
            event_type=event_type,
            supplier_keyword=supplier_keyword,
            yyyymm=yyyymm,
            status=status,
            event_scope=event_scope,
        )

    # ── Dialogs ─────────────────────────────────────────────────────────────

    def _ensure_has_active_suppliers(self) -> bool:
        if event_service.has_active_suppliers():
            return True
        QMessageBox.warning(
            self,
            "需先建立供應商",
            "目前沒有可用供應商，請先到基礎清單建立供應商。",
        )
        self._open_master_data()
        return False

    def open_new_anomaly_dialog(self):
        if not self._ensure_has_active_suppliers():
            return
        dialog = NewAnomalyDialog(self)
        if dialog.exec():
            self.refresh_all_views()

    def open_new_visit_defect_dialog(self):
        if not self._ensure_has_active_suppliers():
            return
        dialog = NewVisitDialog(self, focus_defect_note=True)
        if dialog.exec():
            self.refresh_all_views()

    def open_new_visit_dialog(self):
        if not self._ensure_has_active_suppliers():
            return
        dialog = NewVisitDialog(self)
        if dialog.exec():
            self.refresh_all_views()

    # ── Data refresh ────────────────────────────────────────────────────────

    def refresh_all_views(self):
        self.home_widget.refresh_data()
        self.visit_widget.refresh_data()
        self.visit_anomaly_widget.refresh_data()
        self.standalone_anomaly_widget.refresh_data()
        self.closed_event_widget.refresh_data()
        self.stats_widget.refresh_data()
        self.master_widget.refresh_data()
        self._refresh_sidebar_badge()

    def _refresh_sidebar_badge(self) -> None:
        try:
            summary = event_service.get_dashboard_summary()
            count = int(summary.get("open_count", 0))
        except Exception:
            count = 0
        self.sidebar.set_badge(ANOMALY_PAGE_INDEX, count)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
