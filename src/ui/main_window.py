import logging
import sqlite3
import sys


logger = logging.getLogger(__name__)
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app_version import APP_TITLE
from database.connection import get_connection
from database import repository
from services import event_service as event_service
from services.event import _product_service, _query_service
from ncr.db.database import DatabaseMigrationError
from ncr.models.defect import (
    PROCESSING_LINE_MATERIAL,
    PROCESSING_LINE_OUTSOURCE,
    PROCESSING_LINE_UNCLASSIFIED,
)
from ncr.embed import NCR_PAGE_OFFSET, NCR_PAGE_SPECS, NcrController
import ncr.services.stats_service as ncr_stats_service
from ncr.ui.defect_list import DefectListWidget as NcrDefectListWidget
from ncr.ui.ui_style import app_stylesheet as ncr_app_stylesheet
from ui.layout_constants import (
    MAIN_WINDOW_DEFAULT_HEIGHT,
    MAIN_WINDOW_DEFAULT_WIDTH,
    MAIN_WINDOW_MAX_HEIGHT,
    MAIN_WINDOW_MAX_WIDTH,
    MAIN_WINDOW_MIN_HEIGHT,
    MAIN_WINDOW_MIN_WIDTH,
)
from ui.page_header_bar import PageHeaderBar
from ui.sidebar_nav import (
    PAGE_HOME,
    PAGE_MASTER,
    PAGE_NCR,
    PAGE_NCR_CREATE,
    PAGE_NCR_HISTORY,
    PAGE_NCR_PENDING,
    PAGE_NCR_PENDING_MATERIAL,
    PAGE_NCR_PENDING_OUTSOURCE,
    PAGE_NCR_STATS,
    PAGE_STATS,
    SidebarNav,
)
from ui.theme import asset_path
from ui.window_sizing import fit_widget_to_available_screen
from ui.widgets.common_widgets import EmptyStateWidget
from ui.widgets.new_anomaly_dialog import NewAnomalyDialog
from ui.widgets.new_visit_dialog import NewVisitDialog
from ui.widgets.defect_list_widget import EventListWidget
from ui.widgets.home_widget import HomeWidget
from ui.widgets.master_data_widget import MasterDataWidget
from ui.widgets.stats_view_widget import StatsViewWidget
from ui.widgets.ncr_stats_widget import NcrStatsWidget

HOME_PAGE_INDEX = 0
EVENT_PAGE_INDEX = 1
STATS_PAGE_INDEX = 2
NCR_PAGE_COUNT = len(NCR_PAGE_SPECS)
NCR_ENTRY_PAGE_INDEX = NCR_PAGE_OFFSET + 0
NCR_PENDING_OUTSOURCE_PAGE_INDEX = NCR_PAGE_OFFSET + 1
NCR_PENDING_MATERIAL_PAGE_INDEX = NCR_PAGE_OFFSET + 2
NCR_TRACE_PAGE_INDEX = NCR_PAGE_OFFSET + 3
# Compatibility alias: the retired generic pending route lands on the first
# formal processing line. New navigation must use the two explicit page keys.
NCR_TRACKING_PAGE_INDEX = NCR_PENDING_OUTSOURCE_PAGE_INDEX
NCR_PAGE_INDEX = NCR_TRACKING_PAGE_INDEX
NCR_STATS_PAGE_INDEX = NCR_PAGE_OFFSET + NCR_PAGE_COUNT
MASTER_PAGE_INDEX = NCR_STATS_PAGE_INDEX + 1

_PAGE_TITLES = {
    HOME_PAGE_INDEX:  ("首頁", "Mitcorp SQE Tool"),
    EVENT_PAGE_INDEX: ("事件管理", "供應商事件：訪廠、訪廠發現異常、單獨異常與已結案查詢"),
    STATS_PAGE_INDEX: ("異常事件統計", "供應商事件趨勢、責任人績效與供應商風險"),
    NCR_STATS_PAGE_INDEX: ("不合格品統計分析", "倉庫實物不合格品統計圖表與比例分析"),
    MASTER_PAGE_INDEX: ("基礎資料", "供應商與品名主檔管理"),
}

# Compatibility alias kept for external callers
NCR_HOME_PAGE_INDEX = NCR_TRACKING_PAGE_INDEX

for _i, (_label, _title, _subtitle) in enumerate(NCR_PAGE_SPECS):
    _PAGE_TITLES[NCR_PAGE_OFFSET + _i] = (_title, _subtitle)

# 側欄 PAGE_KEY ↔ QStackedWidget 索引對應（側欄不耦合堆疊索引，由此處轉換）。
_PAGE_KEY_TO_INDEX = {
    PAGE_HOME: HOME_PAGE_INDEX,
    PAGE_STATS: STATS_PAGE_INDEX,
    PAGE_NCR: NCR_TRACKING_PAGE_INDEX,
    PAGE_NCR_CREATE: NCR_ENTRY_PAGE_INDEX,
    PAGE_NCR_PENDING: NCR_TRACKING_PAGE_INDEX,
    PAGE_NCR_PENDING_OUTSOURCE: NCR_PENDING_OUTSOURCE_PAGE_INDEX,
    PAGE_NCR_PENDING_MATERIAL: NCR_PENDING_MATERIAL_PAGE_INDEX,
    PAGE_NCR_HISTORY: NCR_TRACE_PAGE_INDEX,
    PAGE_NCR_STATS: NCR_STATS_PAGE_INDEX,
    PAGE_MASTER: MASTER_PAGE_INDEX,
}
_PAGE_INDEX_TO_KEY = {index: key for key, index in _PAGE_KEY_TO_INDEX.items()}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
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
        self.sidebar.nav_activated.connect(self._on_nav_activated)
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
        # Consolidated event-management page: one EventListWidget whose scope is
        # selected by the sidebar rows 單獨異常 / 訪廠發現異常 / 訪廠紀錄 / 已結案.
        self.events_widget = EventListWidget(self, mode="query", fixed_scope=None, lazy_load=True)
        self.stats_widget = StatsViewWidget(self, lazy_load=True)
        self.ncr_stats_widget = NcrStatsWidget(self, lazy_load=True)
        self.master_widget = MasterDataWidget(self, lazy_load=True)

        self.stack.insertWidget(HOME_PAGE_INDEX,  self.home_widget)
        self.stack.insertWidget(EVENT_PAGE_INDEX, self.events_widget)
        self.stack.insertWidget(STATS_PAGE_INDEX, self.stats_widget)

        # ── 嵌入倉庫不合格品實物管理模組頁面（索引 3/4/5/6）──
        # NCR 資料庫問題不可拖垮主程式；失敗時以 placeholder 佔位並保持索引對齊。
        try:
            self.ncr = NcrController(self, lazy_load=True)
            for offset_idx, ncr_page in enumerate(self.ncr.pages()):
                self.stack.insertWidget(NCR_PAGE_OFFSET + offset_idx, ncr_page)
        except (DatabaseMigrationError, sqlite3.Error) as exc:
            self.ncr = None
            self._insert_ncr_placeholders(str(exc))
        self.home_widget.refresh_data()

        # ── 不合格品統計分析（索引 7）──
        self.stack.insertWidget(NCR_STATS_PAGE_INDEX, self.ncr_stats_widget)

        # ── 基礎資料（索引 8）──
        self.stack.insertWidget(MASTER_PAGE_INDEX, self.master_widget)

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
            label = NCR_PAGE_SPECS[offset_idx][0]
            placeholder = EmptyStateWidget(
                f"{label}暫時無法載入",
                f"原因：{reason}\n\n"
                "請嘗試重新啟動程式；若持續發生，請確認資料庫檔案是否存在或損毀後再試。",
            )
            placeholder.setObjectName("NcrUnavailablePlaceholder")
            self.stack.insertWidget(NCR_PAGE_OFFSET + offset_idx, placeholder)

    # ── Navigation ──────────────────────────────────────────────────────────

    def _is_ncr_index(self, index: int) -> bool:
        return NCR_PAGE_OFFSET <= index < NCR_PAGE_OFFSET + NCR_PAGE_COUNT

    def _switch_primary_page(self, page_index: int) -> None:
        count = self.stack.count()
        if page_index < 0 or page_index >= count:
            return
        
        # 觸發延遲載入 (Lazy loading) 與統計頁面強制整理
        widget = self.stack.widget(page_index)
        if widget is not None:
            if page_index in (STATS_PAGE_INDEX, NCR_STATS_PAGE_INDEX):
                if hasattr(widget, "refresh_data"):
                    widget.refresh_data()
            elif hasattr(widget, "_has_loaded") and not getattr(widget, "_has_loaded", False):
                if hasattr(widget, "refresh_data"):
                    widget.refresh_data()

        self.stack.setCurrentIndex(page_index)
        self._sync_sidebar_active(page_index)
        title, subtitle = _PAGE_TITLES.get(page_index, ("", ""))
        self._header_bar.set_page(title, subtitle)
        if self.ncr is not None and self._is_ncr_index(page_index):
            self.ncr.refresh_for_local_index(page_index - NCR_PAGE_OFFSET)

    def _action_target_index(self, action) -> int:
        kind, value = action
        if kind == "scope":
            return EVENT_PAGE_INDEX
        return _PAGE_KEY_TO_INDEX.get(value, -1)

    def _sync_sidebar_active(self, page_index: int) -> None:
        """依目前頁面（事件頁則依目前 scope）高亮對應的側欄導覽列。"""
        if page_index == EVENT_PAGE_INDEX:
            scope = getattr(self.events_widget, "_filter_event_scope", None)
            self.sidebar.set_active(("scope", scope))
        else:
            key = _PAGE_INDEX_TO_KEY.get(page_index)
            if key is not None:
                self.sidebar.set_active(("page", key))

    def _on_nav_activated(self, action) -> None:
        kind, value = action
        # 離開含未存資料的 NCR 頁面前先確認（NCR 內建髒資料守衛）。
        current = self.stack.currentIndex()
        if (
            self.ncr is not None
            and self._is_ncr_index(current)
            and self._action_target_index(action) != current
            and not self.ncr.confirm_can_leave(current - NCR_PAGE_OFFSET)
        ):
            return  # 取消導覽；側欄高亮未變更，無需還原。
        if kind == "page":
            page_index = _PAGE_KEY_TO_INDEX.get(value)
            if page_index is None:
                return
            if page_index == MASTER_PAGE_INDEX:
                self._open_master_data()
            else:
                self._switch_primary_page(page_index)
        elif kind == "scope":
            self._switch_primary_page(EVENT_PAGE_INDEX)
            self.events_widget.set_event_scope(value)
            self._sync_sidebar_active(EVENT_PAGE_INDEX)

    def show_ncr_status(self, message: str, timeout_ms: int = 5000) -> None:
        """顯示 NCR 模組的狀態訊息（例如已建立不良單）於主視窗狀態列。"""
        self.statusBar().showMessage(message, timeout_ms)

    def _open_master_data(self) -> None:
        self._switch_primary_page(MASTER_PAGE_INDEX)

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
        # apply_quick_filters 更新了 scope，重新同步側欄高亮到對應 scope 列。
        self._sync_sidebar_active(EVENT_PAGE_INDEX)

    # ── Dialogs ─────────────────────────────────────────────────────────────

    def _ensure_has_active_suppliers(self) -> bool:
        if _product_service.has_active_suppliers():
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
        dialog = NewVisitDialog(self)
        if dialog.exec():
            self.refresh_all_views()

    def open_new_visit_dialog(self):
        if not self._ensure_has_active_suppliers():
            return
        dialog = NewVisitDialog(self)
        if dialog.exec():
            self.refresh_all_views()

    def open_warehouse_nonconforming_tracker(self) -> None:
        """Compatibility route for older callers; opens the outsource pending line."""
        self.open_warehouse_pending_outsource()

    def open_warehouse_pending_outsource(self) -> None:
        """切換至嵌入式倉庫待處理委外加工頁（同一視窗內）。"""
        self._switch_primary_page(NCR_PENDING_OUTSOURCE_PAGE_INDEX)

    def open_warehouse_pending_material(self) -> None:
        """切換至嵌入式倉庫待處理原物料頁（同一視窗內）。"""
        self._switch_primary_page(NCR_PENDING_MATERIAL_PAGE_INDEX)

    def open_warehouse_unclassified_pending(self) -> None:
        """Open migrated warehouse records that still need a formal processing line."""
        if self.ncr is None:
            QMessageBox.warning(self, "倉庫模組未載入", "目前無法開啟未分流待整理清單。")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("未分流待整理")
        dialog.setStyleSheet(ncr_app_stylesheet())
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(8, 12, 8, 8)
        widget = NcrDefectListWidget(
            self.ncr.conn,
            dialog,
            workflow="tracking",
            processing_line=PROCESSING_LINE_UNCLASSIFIED,
        )
        widget.changed.connect(self.refresh_all_views)
        layout.addWidget(widget)
        dialog.resize(1100, 680)
        dialog.exec()
        # 整理後同步刷新倉庫清單頁(含待處理頁的未分流提示計數)與其餘 views。
        if self.ncr is not None:
            self.ncr.refresh_all()
        else:
            self.refresh_all_views()

    def open_warehouse_nonconforming_create(self) -> None:
        """切換至嵌入式倉庫不合格品建立表單。"""
        self._switch_primary_page(NCR_ENTRY_PAGE_INDEX)
        if self.ncr is not None:
            self.ncr.open_create_entry()

    # ── Data refresh ────────────────────────────────────────────────────────

    def refresh_all_views(self):
        self.home_widget.refresh_data()
        self.events_widget.refresh_data()
        self.stats_widget.refresh_data()
        self.ncr_stats_widget.refresh_data()
        self.master_widget.refresh_data()
        self._refresh_sidebar_badge()

    def _refresh_sidebar_badge(self) -> None:
        try:
            summary = _query_service.get_dashboard_summary()
            count = int(summary.get("standalone_open_count", 0))
        except Exception:
            logger.exception("重新整理事件徽章失敗")
            count = 0
        self.sidebar.set_badge(("scope", repository.EVENT_SCOPE_ANOMALY_ONLY), count)
        try:
            with get_connection() as conn:
                warehouse_counts = ncr_stats_service.get_pending_counts_by_processing_line(conn)
            outsource_count = int(warehouse_counts.get(PROCESSING_LINE_OUTSOURCE, 0))
            material_count = int(warehouse_counts.get(PROCESSING_LINE_MATERIAL, 0))
        except Exception:
            logger.exception("重新整理倉庫徽章失敗")
            outsource_count = 0
            material_count = 0
        self.sidebar.set_badge(("page", PAGE_NCR_PENDING_OUTSOURCE), outsource_count)
        self.sidebar.set_badge(("page", PAGE_NCR_PENDING_MATERIAL), material_count)

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
