import sqlite3
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from database.connection import get_connection
from services import event_service
from ncr.db.database import DatabaseMigrationError
from ncr.embed import NCR_PAGE_OFFSET, NCR_PAGE_SPECS, NcrController
import ncr.services.stats_service as ncr_stats_service
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
EVENT_PAGE_INDEX = 1
STATS_PAGE_INDEX = 2
MASTER_PAGE_INDEX = 3

# Legacy index aliases kept for external callers. The consolidated event-management
# page (index 1) absorbed the former 異常一覽表 / 訪廠紀錄一覽表 / 異常已結案查詢 pages,
# which are now scope tabs inside that single page.
ANOMALY_PAGE_INDEX = EVENT_PAGE_INDEX
VISIT_PAGE_INDEX = EVENT_PAGE_INDEX
CLOSED_PAGE_INDEX = EVENT_PAGE_INDEX
VISIT_ANOMALY_PAGE_INDEX = EVENT_PAGE_INDEX
STANDALONE_ANOMALY_PAGE_INDEX = EVENT_PAGE_INDEX

_PAGE_TITLES = {
    HOME_PAGE_INDEX:  ("首頁", "Mitcorp SQE Tool"),
    EVENT_PAGE_INDEX: ("事件管理", "供應商事件：訪廠、訪廠發現異常、單獨異常與已結案查詢"),
    STATS_PAGE_INDEX: ("異常事件統計", "供應商事件統計與倉庫不合格品實物統計"),
    MASTER_PAGE_INDEX: ("基礎資料", "供應商與品名主檔管理"),
}

# Embedded warehouse nonconforming-product page occupies stack index 6.
NCR_PAGE_INDEX = NCR_PAGE_OFFSET + 0
NCR_PAGE_COUNT = len(NCR_PAGE_SPECS)

# Compatibility aliases kept for external callers
NCR_HOME_PAGE_INDEX = NCR_PAGE_INDEX
NCR_ENTRY_PAGE_INDEX = NCR_PAGE_INDEX
NCR_TRACKING_PAGE_INDEX = NCR_PAGE_INDEX
NCR_TRACE_PAGE_INDEX = NCR_PAGE_INDEX
NCR_ANALYSIS_PAGE_INDEX = NCR_PAGE_INDEX
NCR_PRODUCT_PAGE_INDEX = NCR_PAGE_INDEX
NCR_SUPPLIER_PAGE_INDEX = NCR_PAGE_INDEX

for _i, (_label, _title, _subtitle) in enumerate(NCR_PAGE_SPECS):
    _PAGE_TITLES[NCR_PAGE_OFFSET + _i] = (_title, _subtitle)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SQE DailyWork - SQE 工作台")
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
        self.ncr: NcrController | None = None
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
        self.sidebar.warehouse_create_clicked.connect(
            self.open_warehouse_nonconforming_create
        )
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
        # Consolidated event-management page: a single EventListWidget whose scope
        # tabs cover 單獨異常 / 訪廠發現異常 / 訪廠紀錄 / 已結案 (see EVENT_QUERY_SCOPE_TABS).
        self.events_widget = EventListWidget(self, mode="query", fixed_scope=None)
        self.stats_widget = StatsViewWidget(self)
        self.master_widget = MasterDataWidget(self)

        self.stack.insertWidget(HOME_PAGE_INDEX,  self.home_widget)
        self.stack.insertWidget(EVENT_PAGE_INDEX, self.events_widget)
        self.stack.insertWidget(STATS_PAGE_INDEX, self.stats_widget)
        self.stack.insertWidget(MASTER_PAGE_INDEX, self.master_widget)

        # ── 嵌入倉庫不合格品實物管理模組頁面（索引 6）──
        # NCR 資料庫問題不可拖垮主程式；失敗時以 placeholder 佔位並保持索引對齊。
        try:
            self.ncr = NcrController(self)
            for offset_idx, ncr_page in enumerate(self.ncr.pages()):
                self.stack.insertWidget(NCR_PAGE_OFFSET + offset_idx, ncr_page)
        except (DatabaseMigrationError, sqlite3.Error) as exc:
            self.ncr = None
            self._insert_ncr_placeholders(str(exc))

        # Compatibility aliases used by tests / older callers. Every former event
        # entry now resolves to the single consolidated event-management page.
        self.entry_widget = self.events_widget
        self.standalone_anomaly_widget = self.events_widget
        self.visit_widget = self.events_widget
        self.closed_event_widget = self.events_widget
        self.visit_anomaly_widget = self.events_widget

        content_layout.addWidget(self.stack, 1)
        root.addWidget(content_area, 1)

        self._switch_primary_page(HOME_PAGE_INDEX)

    def _insert_ncr_placeholders(self, reason: str) -> None:
        """NCR 載入失敗時插入佔位頁，維持側欄索引與嵌入頁對齊。"""
        for offset_idx in range(NCR_PAGE_COUNT):
            placeholder = QLabel(
                f"倉庫不合格品追蹤模組暫時無法載入。\n\n{reason}"
            )
            placeholder.setObjectName("NcrUnavailablePlaceholder")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setWordWrap(True)
            self.stack.insertWidget(NCR_PAGE_OFFSET + offset_idx, placeholder)

    # ── Navigation ──────────────────────────────────────────────────────────

    def _is_ncr_index(self, index: int) -> bool:
        return NCR_PAGE_OFFSET <= index < NCR_PAGE_OFFSET + NCR_PAGE_COUNT

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
        if self.ncr is not None and self._is_ncr_index(page_index):
            self.ncr.refresh_for_local_index(page_index - NCR_PAGE_OFFSET)

    def _on_sidebar_page_changed(self, index: int) -> None:
        # 離開含未存資料的 NCR 頁面前先確認（NCR 內建髒資料守衛）
        current = self.stack.currentIndex()
        if self.ncr is not None and self._is_ncr_index(current):
            if not self.ncr.confirm_can_leave(current - NCR_PAGE_OFFSET):
                self.sidebar.set_active(current)  # 還原側欄高亮
                return
        if index == MASTER_PAGE_INDEX:
            self._open_master_data()
        else:
            self._switch_primary_page(index)

    def show_ncr_status(self, message: str, timeout_ms: int = 5000) -> None:
        """顯示 NCR 模組的狀態訊息（例如已建立不良單）於主視窗狀態列。"""
        self.statusBar().showMessage(message, timeout_ms)

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
        overdue_only: bool = False,
    ) -> None:
        # Single consolidated event page: switch then let the widget activate the
        # matching scope tab. Routing the scope through apply_quick_filters makes
        # every KPI / stats drill-down land on the correct scope (this also fixes
        # the former 訪廠發現異常 KPI mismatch, where the scope was dropped by a
        # fixed-scope page).
        self._switch_primary_page(EVENT_PAGE_INDEX)
        self.events_widget.apply_quick_filters(
            event_type=event_type,
            supplier_keyword=supplier_keyword,
            yyyymm=yyyymm,
            status=status,
            event_scope=event_scope,
            overdue_only=overdue_only,
        )

    # ── Dialogs ─────────────────────────────────────────────────────────────

    def _ensure_has_active_suppliers(self) -> bool:
        if event_service.has_active_suppliers():
            return True
        QMessageBox.warning(
            self,
            "需先建立供應商",
            "目前沒有可用供應商，請先到基礎資料建立供應商。",
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

    def open_warehouse_nonconforming_tracker(self) -> None:
        """切換至嵌入式倉庫不合格品追蹤模組（同一視窗內）。"""
        self._switch_primary_page(NCR_HOME_PAGE_INDEX)

    def open_warehouse_nonconforming_create(self) -> None:
        """切換至嵌入式倉庫不合格品建立表單。"""
        self._switch_primary_page(NCR_HOME_PAGE_INDEX)
        if self.ncr is not None:
            self.ncr.open_create_entry()

    # ── Data refresh ────────────────────────────────────────────────────────

    def refresh_all_views(self):
        self.home_widget.refresh_data()
        self.events_widget.refresh_data()
        self.stats_widget.refresh_data()
        self.master_widget.refresh_data()
        self._refresh_sidebar_badge()

    def _refresh_sidebar_badge(self) -> None:
        try:
            summary = event_service.get_dashboard_summary()
            count = int(summary.get("open_count", 0))
        except Exception:
            count = 0
        self.sidebar.set_badge(EVENT_PAGE_INDEX, count)
        try:
            with get_connection() as conn:
                warehouse_summary = ncr_stats_service.get_warehouse_nonconforming_summary(conn)
            warehouse_count = int(warehouse_summary.get("open_count", 0))
        except Exception:
            warehouse_count = 0
        self.sidebar.set_badge(NCR_PAGE_INDEX, warehouse_count)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):  # noqa: N802
        # NCR 嵌入頁有未存資料則攔截關閉；否則關閉共用 DB 連線。
        if self.ncr is not None:
            for local_index in range(NCR_PAGE_COUNT):
                if not self.ncr.confirm_can_leave(local_index):
                    event.ignore()
                    return
            self.ncr.close()
        event.accept()


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
