from __future__ import annotations

import logging
import sqlite3
import sys
from typing import Any



logger = logging.getLogger(__name__)
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app_version import APP_TITLE
from database.connection import disposable_runtime_enabled, get_connection
from database import repository
from services.appearance_preferences_service import load_application_preferences
from services.event import _product_service, _query_service
from ncr.db.database import DatabaseMigrationError
from ncr.models.defect import (
    PROCESSING_LINE_MATERIAL,
    PROCESSING_LINE_OUTSOURCE,
    PROCESSING_LINE_UNCLASSIFIED,
)
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
from ui.runtime_mode import is_automated_runtime, missing_supplier_create_gate
from ui.page_header_bar import PageHeaderBar
from ui.sidebar_nav import (
    ACTION_OPEN_APPEARANCE_REDESIGN,
    PAGE_ANOMALY_CREATE,
    PAGE_EVENT_OPEN_ACTIONS,
    PAGE_EVENT_OVERDUE,
    PAGE_EVENT_QUERY,
    PAGE_EVENT_ROOT_CAUSE,
    PAGE_HOME,
    PAGE_MANAGER_VIEW,
    PAGE_MASTER,
    PAGE_SUPPLIER_OVERVIEW,
    PAGE_NCR,
    PAGE_NCR_CREATE,
    PAGE_NCR_HISTORY,
    PAGE_NCR_PENDING,
    PAGE_NCR_PENDING_MATERIAL,
    PAGE_NCR_PENDING_OUTSOURCE,
    PAGE_NCR_STATS,
    PAGE_STATS,
    PAGE_VISIT_CREATE,
    SidebarNav,
)
from ui.theme import asset_path
from ui.window_sizing import (
    fit_widget_to_available_screen,
    restore_or_fit_window_geometry,
)
from ui.widgets.common_widgets import EmptyStateWidget
from ui.widgets.home_widget import HomeWidget
from ui.widgets.lazy_page_widget import LazyPageWidget
from ui.widgets.anomaly_management_page import AnomalyManagementPage
from ui.widgets.manager_view_page import ManagerViewPage
from ui.widgets.supplier_360_page import Supplier360Page
from ui.widgets.supplier_event_queue_page import SupplierEventQueuePage
from ui.widgets.supplier_overview_page import SupplierOverviewPage

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
VISIT_CREATE_PAGE_INDEX = MASTER_PAGE_INDEX + 1
ANOMALY_CREATE_PAGE_INDEX = MASTER_PAGE_INDEX + 2
ANOMALY_MANAGEMENT_PAGE_INDEX = ANOMALY_CREATE_PAGE_INDEX + 1
SUPPLIER_OVERVIEW_PAGE_INDEX = ANOMALY_MANAGEMENT_PAGE_INDEX + 1
SUPPLIER_360_PAGE_INDEX = SUPPLIER_OVERVIEW_PAGE_INDEX + 1
MANAGER_VIEW_PAGE_INDEX = SUPPLIER_360_PAGE_INDEX + 1
EVENT_OVERDUE_QUEUE_PAGE_INDEX = MANAGER_VIEW_PAGE_INDEX + 1
EVENT_ROOT_CAUSE_QUEUE_PAGE_INDEX = MANAGER_VIEW_PAGE_INDEX + 2
EVENT_OPEN_ACTIONS_QUEUE_PAGE_INDEX = MANAGER_VIEW_PAGE_INDEX + 3
EVENT_CREATE_VISIT_PAGE_INDEX = VISIT_CREATE_PAGE_INDEX
EVENT_CREATE_ANOMALY_PAGE_INDEX = ANOMALY_CREATE_PAGE_INDEX

_PAGE_TITLES = {
    HOME_PAGE_INDEX:  ("首頁", "Mitcorp SQE Tool"),
    EVENT_PAGE_INDEX: ("事件管理", "供應商事件：訪廠、訪廠發現異常、單獨異常與已結案查詢"),
    STATS_PAGE_INDEX: ("異常事件統計", "供應商事件趨勢、責任人績效與供應商風險"),
    NCR_STATS_PAGE_INDEX: ("不合格品統計分析", "倉庫實物不合格品統計圖表與比例分析"),
    MASTER_PAGE_INDEX: ("基礎資料", "供應商與品名主檔管理"),
    VISIT_CREATE_PAGE_INDEX: ("新增訪廠", "建立供應商訪廠紀錄"),
    ANOMALY_CREATE_PAGE_INDEX: ("新增異常", "建立供應商異常事件單"),
    ANOMALY_MANAGEMENT_PAGE_INDEX: ("異常案件管理", "查看與維護單一供應商異常案件"),
    SUPPLIER_OVERVIEW_PAGE_INDEX: ("供應商總覽", "依供應商查看異常、訪廠與不合格品品質狀況"),
    SUPPLIER_360_PAGE_INDEX: ("供應商檔案", "供應商事件、訪廠與不合格品的唯讀聚合視角"),
    MANAGER_VIEW_PAGE_INDEX: ("主管檢視", "案件總覽與品質狀態營運分析"),
    EVENT_OVERDUE_QUEUE_PAGE_INDEX: ("逾期未結", "待處理且逾期的供應商異常作業佇列"),
    EVENT_ROOT_CAUSE_QUEUE_PAGE_INDEX: ("待根本原因", "根本原因尚未完成的待處理異常"),
    EVENT_OPEN_ACTIONS_QUEUE_PAGE_INDEX: ("進行中處置", "待處理異常的已規劃／執行中處置"),
}

# Compatibility alias kept for external callers
NCR_HOME_PAGE_INDEX = NCR_TRACKING_PAGE_INDEX

for _i, (_label, _title, _subtitle) in enumerate(NCR_PAGE_SPECS):
    _PAGE_TITLES[NCR_PAGE_OFFSET + _i] = (_title, _subtitle)

# 側欄 PAGE_KEY ↔ QStackedWidget 索引對應（側欄不耦合堆疊索引，由此處轉換）。
_PAGE_KEY_TO_INDEX = {
    PAGE_HOME: HOME_PAGE_INDEX,
    PAGE_EVENT_QUERY: EVENT_PAGE_INDEX,
    PAGE_EVENT_OVERDUE: EVENT_OVERDUE_QUEUE_PAGE_INDEX,
    PAGE_EVENT_ROOT_CAUSE: EVENT_ROOT_CAUSE_QUEUE_PAGE_INDEX,
    PAGE_EVENT_OPEN_ACTIONS: EVENT_OPEN_ACTIONS_QUEUE_PAGE_INDEX,
    PAGE_MANAGER_VIEW: MANAGER_VIEW_PAGE_INDEX,
    PAGE_SUPPLIER_OVERVIEW: SUPPLIER_OVERVIEW_PAGE_INDEX,
    PAGE_STATS: STATS_PAGE_INDEX,
    PAGE_NCR: NCR_TRACKING_PAGE_INDEX,
    PAGE_NCR_CREATE: NCR_ENTRY_PAGE_INDEX,
    PAGE_NCR_PENDING: NCR_TRACKING_PAGE_INDEX,
    PAGE_NCR_PENDING_OUTSOURCE: NCR_PENDING_OUTSOURCE_PAGE_INDEX,
    PAGE_NCR_PENDING_MATERIAL: NCR_PENDING_MATERIAL_PAGE_INDEX,
    PAGE_NCR_HISTORY: NCR_TRACE_PAGE_INDEX,
    PAGE_NCR_STATS: NCR_STATS_PAGE_INDEX,
    PAGE_MASTER: MASTER_PAGE_INDEX,
    PAGE_VISIT_CREATE: VISIT_CREATE_PAGE_INDEX,
    PAGE_ANOMALY_CREATE: ANOMALY_CREATE_PAGE_INDEX,
}
_QUEUE_PAGE_KEYS = frozenset(
    {
        PAGE_EVENT_OVERDUE,
        PAGE_EVENT_ROOT_CAUSE,
        PAGE_EVENT_OPEN_ACTIONS,
    }
)
_PAGE_INDEX_TO_KEY = {index: key for key, index in _PAGE_KEY_TO_INDEX.items()}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(QIcon(str(asset_path("mitcorp_logo.png"))))
        is_automated = is_automated_runtime()
        prefs = load_application_preferences()
        geom = None
        if prefs.window_geometry_mode == "remember" and not is_automated:
            from PySide6.QtCore import QSettings
            settings = QSettings("Mitcorp", "SQEDailyWork")
            geom = settings.value("main_window_geometry")

        restore_or_fit_window_geometry(
            self,
            geometry_mode="fit_screen" if is_automated else prefs.window_geometry_mode,
            geometry_data=geom,
            preferred_width=MAIN_WINDOW_DEFAULT_WIDTH,
            preferred_height=MAIN_WINDOW_DEFAULT_HEIGHT,
            minimum_width=MAIN_WINDOW_MIN_WIDTH,
            minimum_height=MAIN_WINDOW_MIN_HEIGHT,
            maximum_width=MAIN_WINDOW_MAX_WIDTH,
            maximum_height=MAIN_WINDOW_MAX_HEIGHT,
        )

        self._ncr: NcrController | None = None
        self._events_page: QWidget | None = None
        self._stats_page: QWidget | None = None
        self._ncr_stats_page: QWidget | None = None
        self._master_page: QWidget | None = None
        self._new_visit_page: QWidget | None = None
        self._new_anomaly_page: QWidget | None = None
        self._anomaly_management_page: AnomalyManagementPage | None = None
        self._ncr_pages: list[QWidget] = []
        self._setup_ui()
        self._global_search_shortcut = QShortcut(
            QKeySequence("Ctrl+K"),
            self,
            activated=self.open_global_search,
        )
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._refresh_sidebar_badge)
        QTimer.singleShot(100, self._check_startup_unresolved)


    def _ensure_ncr_controller(self) -> NcrController | None:
        """按需初始化倉庫 NCR 控制器。"""
        if self._ncr is None:
            try:
                self._ncr = NcrController(self, lazy_load=True)
            except (DatabaseMigrationError, sqlite3.Error) as exc:
                self._ncr = None
                logger.exception("倉庫 NCR 控制器初始化失敗: %s", exc)
        return self._ncr

    @property
    def ncr(self) -> NcrController | None:
        return self._ensure_ncr_controller()

    @ncr.setter
    def ncr(self, value: NcrController | None) -> None:
        self._ncr = value

    def _get_or_create_events_widget(self) -> Any:
        if isinstance(self._events_page, LazyPageWidget):
            real = self._events_page.ensure_widget()
            idx = self.stack.indexOf(self._events_page)
            if idx >= 0:
                cur = self.stack.currentIndex()
                self.stack.removeWidget(self._events_page)
                self.stack.insertWidget(idx, real)
                if cur == idx:
                    self.stack.setCurrentIndex(idx)
            self._events_page = real
        return self._events_page

    @property
    def events_widget(self) -> Any:
        return self._get_or_create_events_widget()

    @events_widget.setter
    def events_widget(self, value: Any) -> None:
        if self._events_page is not None and self._events_page is not value:
            idx = self.stack.indexOf(self._events_page)
            if idx >= 0:
                self.stack.removeWidget(self._events_page)
                self.stack.insertWidget(idx, value)
        self._events_page = value

    def _get_or_create_stats_widget(self) -> Any:
        if isinstance(self._stats_page, LazyPageWidget):
            real = self._stats_page.ensure_widget()
            idx = self.stack.indexOf(self._stats_page)
            if idx >= 0:
                cur = self.stack.currentIndex()
                self.stack.removeWidget(self._stats_page)
                self.stack.insertWidget(idx, real)
                if cur == idx:
                    self.stack.setCurrentIndex(idx)
            self._stats_page = real
        return self._stats_page

    @property
    def stats_widget(self) -> Any:
        return self._get_or_create_stats_widget()

    @stats_widget.setter
    def stats_widget(self, value: Any) -> None:
        if self._stats_page is not None and self._stats_page is not value:
            idx = self.stack.indexOf(self._stats_page)
            if idx >= 0:
                self.stack.removeWidget(self._stats_page)
                self.stack.insertWidget(idx, value)
        self._stats_page = value

    def _get_or_create_ncr_stats_widget(self) -> Any:
        if isinstance(self._ncr_stats_page, LazyPageWidget):
            real = self._ncr_stats_page.ensure_widget()
            idx = self.stack.indexOf(self._ncr_stats_page)
            if idx >= 0:
                cur = self.stack.currentIndex()
                self.stack.removeWidget(self._ncr_stats_page)
                self.stack.insertWidget(idx, real)
                if cur == idx:
                    self.stack.setCurrentIndex(idx)
            self._ncr_stats_page = real
        return self._ncr_stats_page

    @property
    def ncr_stats_widget(self) -> Any:
        return self._get_or_create_ncr_stats_widget()

    @ncr_stats_widget.setter
    def ncr_stats_widget(self, value: Any) -> None:
        if self._ncr_stats_page is not None and self._ncr_stats_page is not value:
            idx = self.stack.indexOf(self._ncr_stats_page)
            if idx >= 0:
                self.stack.removeWidget(self._ncr_stats_page)
                self.stack.insertWidget(idx, value)
        self._ncr_stats_page = value

    def _get_or_create_master_widget(self) -> Any:
        if isinstance(self._master_page, LazyPageWidget):
            real = self._master_page.ensure_widget()
            idx = self.stack.indexOf(self._master_page)
            if idx >= 0:
                cur = self.stack.currentIndex()
                self.stack.removeWidget(self._master_page)
                self.stack.insertWidget(idx, real)
                if cur == idx:
                    self.stack.setCurrentIndex(idx)
            self._master_page = real
        return self._master_page

    @property
    def master_widget(self) -> Any:
        return self._get_or_create_master_widget()

    @master_widget.setter
    def master_widget(self, value: Any) -> None:
        if self._master_page is not None and self._master_page is not value:
            idx = self.stack.indexOf(self._master_page)
            if idx >= 0:
                self.stack.removeWidget(self._master_page)
                self.stack.insertWidget(idx, value)
        self._master_page = value

    def _get_or_create_new_visit_page(self) -> Any:
        if isinstance(self._new_visit_page, LazyPageWidget):
            real = self._new_visit_page.ensure_widget()
            idx = self.stack.indexOf(self._new_visit_page)
            if idx >= 0:
                cur = self.stack.currentIndex()
                self.stack.removeWidget(self._new_visit_page)
                self.stack.insertWidget(idx, real)
                if cur == idx:
                    self.stack.setCurrentIndex(idx)
            self._new_visit_page = real
        return self._new_visit_page

    @property
    def new_visit_page(self) -> Any:
        return self._get_or_create_new_visit_page()

    @new_visit_page.setter
    def new_visit_page(self, value: Any) -> None:
        if self._new_visit_page is not None and self._new_visit_page is not value:
            idx = self.stack.indexOf(self._new_visit_page)
            if idx >= 0:
                self.stack.removeWidget(self._new_visit_page)
                self.stack.insertWidget(idx, value)
        self._new_visit_page = value

    def _get_or_create_new_anomaly_page(self) -> Any:
        if isinstance(self._new_anomaly_page, LazyPageWidget):
            real = self._new_anomaly_page.ensure_widget()
            idx = self.stack.indexOf(self._new_anomaly_page)
            if idx >= 0:
                cur = self.stack.currentIndex()
                self.stack.removeWidget(self._new_anomaly_page)
                self.stack.insertWidget(idx, real)
                if cur == idx:
                    self.stack.setCurrentIndex(idx)
            self._new_anomaly_page = real
        return self._new_anomaly_page

    @property
    def new_anomaly_page(self) -> Any:
        return self._get_or_create_new_anomaly_page()

    @new_anomaly_page.setter
    def new_anomaly_page(self, value: Any) -> None:
        if self._new_anomaly_page is not None and self._new_anomaly_page is not value:
            idx = self.stack.indexOf(self._new_anomaly_page)
            if idx >= 0:
                self.stack.removeWidget(self._new_anomaly_page)
                self.stack.insertWidget(idx, value)
        self._new_anomaly_page = value

    @property
    def entry_widget(self) -> Any:
        return self.events_widget

    @property
    def standalone_anomaly_widget(self) -> Any:
        return self.events_widget

    @property
    def visit_widget(self) -> Any:
        return self.events_widget

    @property
    def closed_event_widget(self) -> Any:
        return self.events_widget

    @property
    def visit_anomaly_widget(self) -> Any:
        return self.events_widget

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
        self._global_search_button = QPushButton("搜尋")
        self._global_search_button.setObjectName("GlobalSearchHeaderButton")
        self._global_search_button.setProperty("variant", "secondary")
        self._global_search_button.setAccessibleName("全域搜尋")
        self._global_search_button.setToolTip("開啟全域搜尋（Ctrl+K）")
        self._global_search_button.clicked.connect(self.open_global_search)
        self._header_bar.add_action_widget(self._global_search_button)
        content_layout.addWidget(self._header_bar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("PageStack")

        self.home_widget = HomeWidget(self)

        def _create_events_widget():
            from ui.widgets.defect_list_widget import EventListWidget
            return EventListWidget(self, mode="query", fixed_scope=None, lazy_load=False)

        def _create_visit_create_page():
            from ui.widgets.event_create_page import EventCreatePage
            return EventCreatePage(self, "visit")

        def _create_anomaly_create_page():
            from ui.widgets.event_create_page import EventCreatePage
            return EventCreatePage(self, "anomaly")

        def _create_stats_widget():
            from ui.widgets.stats_view_widget import StatsViewWidget
            return StatsViewWidget(self, lazy_load=True)

        def _create_ncr_stats_widget():
            from ui.widgets.ncr_stats_widget import NcrStatsWidget
            return NcrStatsWidget(self, lazy_load=True)

        def _create_master_widget():
            from ui.widgets.master_data_widget import MasterDataWidget
            return MasterDataWidget(self, lazy_load=True)

        self._events_page = LazyPageWidget(_create_events_widget, object_name="LazyEventsPage")
        self._new_visit_page = LazyPageWidget(_create_visit_create_page, object_name="LazyVisitCreatePage")
        self._new_anomaly_page = LazyPageWidget(_create_anomaly_create_page, object_name="LazyAnomalyCreatePage")
        self._stats_page = LazyPageWidget(_create_stats_widget, object_name="LazyStatsPage")
        self._ncr_stats_page = LazyPageWidget(_create_ncr_stats_widget, object_name="LazyNcrStatsPage")
        self._master_page = LazyPageWidget(_create_master_widget, object_name="LazyMasterPage")
        self._supplier_overview_page = SupplierOverviewPage(self)
        self._supplier_overview_page.supplier_selected.connect(self.open_supplier_360)
        self._supplier_360_page = Supplier360Page(self, self)
        self._manager_view_page = ManagerViewPage(self)
        self._event_overdue_queue_page = SupplierEventQueuePage(
            self,
            queue="overdue",
            page_key=PAGE_EVENT_OVERDUE,
        )
        self._event_root_cause_queue_page = SupplierEventQueuePage(
            self,
            queue="root_cause",
            page_key=PAGE_EVENT_ROOT_CAUSE,
        )
        self._event_open_actions_queue_page = SupplierEventQueuePage(
            self,
            queue="open_actions",
            page_key=PAGE_EVENT_OPEN_ACTIONS,
        )
        self._workbench_source_page_key: str | None = None

        self.stack.insertWidget(HOME_PAGE_INDEX,  self.home_widget)
        self.stack.insertWidget(EVENT_PAGE_INDEX, self._events_page)
        self.stack.insertWidget(STATS_PAGE_INDEX, self._stats_page)

        # ── 嵌入倉庫不合格品實物管理模組頁面（索引 3/4/5/6）──
        # NCR 資料庫問題不可拖垮主程式；失敗時以 placeholder 佔位並保持索引對齊。
        try:
            self._ncr = NcrController(self, lazy_load=True)
            for offset_idx, ncr_page in enumerate(self._ncr.pages()):
                self.stack.insertWidget(NCR_PAGE_OFFSET + offset_idx, ncr_page)
        except (DatabaseMigrationError, sqlite3.Error) as exc:
            self._ncr = None
            self._insert_ncr_placeholders(str(exc))

        # ── 不合格品統計分析（索引 7）──
        self.stack.insertWidget(NCR_STATS_PAGE_INDEX, self._ncr_stats_page)

        # ── 基礎資料（索引 8）──
        self.stack.insertWidget(MASTER_PAGE_INDEX, self._master_page)

        # ── 供應商事件全頁建立表單（索引 9/10）──
        self.stack.insertWidget(VISIT_CREATE_PAGE_INDEX, self._new_visit_page)
        self.stack.insertWidget(ANOMALY_CREATE_PAGE_INDEX, self._new_anomaly_page)
        self._anomaly_management_page = AnomalyManagementPage(self, self)
        self.stack.insertWidget(ANOMALY_MANAGEMENT_PAGE_INDEX, self._anomaly_management_page)
        self.stack.insertWidget(SUPPLIER_OVERVIEW_PAGE_INDEX, self._supplier_overview_page)
        self.stack.insertWidget(SUPPLIER_360_PAGE_INDEX, self._supplier_360_page)
        self.stack.insertWidget(MANAGER_VIEW_PAGE_INDEX, self._manager_view_page)
        self.stack.insertWidget(EVENT_OVERDUE_QUEUE_PAGE_INDEX, self._event_overdue_queue_page)
        self.stack.insertWidget(EVENT_ROOT_CAUSE_QUEUE_PAGE_INDEX, self._event_root_cause_queue_page)
        self.stack.insertWidget(
            EVENT_OPEN_ACTIONS_QUEUE_PAGE_INDEX,
            self._event_open_actions_queue_page,
        )

        content_layout.addWidget(self.stack, 1)
        root.addWidget(content_area, 1)

        prefs = load_application_preferences()
        startup_map = {
            "home": HOME_PAGE_INDEX,
            "events": EVENT_PAGE_INDEX,
            "defects": NCR_PAGE_OFFSET,
            "stats": STATS_PAGE_INDEX,
        }
        initial_index = startup_map.get(prefs.default_startup_page, HOME_PAGE_INDEX)
        self._switch_primary_page(initial_index)

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

        current_index = self.stack.currentIndex()
        if (
            current_index == ANOMALY_MANAGEMENT_PAGE_INDEX
            and page_index != current_index
            and self._anomaly_management_page is not None
            and not self._anomaly_management_page.can_leave()
        ):
            return

        if page_index in (VISIT_CREATE_PAGE_INDEX, ANOMALY_CREATE_PAGE_INDEX):
            if not self._ensure_has_active_suppliers():
                return
        
        # 觸發延遲載入 (Lazy loading) 與統計頁面強制整理
        widget = self.stack.widget(page_index)
        real_widget = None
        should_refresh = False
        if widget is not None:
            if hasattr(widget, "ensure_widget"):
                real_widget = widget.ensure_widget()
            else:
                real_widget = widget

            if page_index in (
                STATS_PAGE_INDEX,
                NCR_STATS_PAGE_INDEX,
                SUPPLIER_OVERVIEW_PAGE_INDEX,
                SUPPLIER_360_PAGE_INDEX,
                MANAGER_VIEW_PAGE_INDEX,
                EVENT_OVERDUE_QUEUE_PAGE_INDEX,
                EVENT_ROOT_CAUSE_QUEUE_PAGE_INDEX,
                EVENT_OPEN_ACTIONS_QUEUE_PAGE_INDEX,
            ):
                should_refresh = hasattr(real_widget, "refresh_data")
            elif hasattr(real_widget, "_has_loaded") and not getattr(real_widget, "_has_loaded", False):
                should_refresh = hasattr(real_widget, "refresh_data")

        if should_refresh:
            self.statusBar().showMessage("載入中...", 0)
            try:
                real_widget.refresh_data()
            finally:
                self.statusBar().clearMessage()

        self.stack.setCurrentIndex(page_index)
        self._sync_sidebar_active(page_index)
        title, subtitle = _PAGE_TITLES.get(page_index, ("", ""))
        self._header_bar.set_page(title, subtitle)
        if self._ncr is not None and self._is_ncr_index(page_index):
            self._ncr.refresh_for_local_index(page_index - NCR_PAGE_OFFSET)

    def _action_target_index(self, action) -> int:
        kind, value = action
        if kind == "scope":
            return EVENT_PAGE_INDEX
        return _PAGE_KEY_TO_INDEX.get(value, -1)

    def _sync_sidebar_active(self, page_index: int) -> None:
        """依目前頁面高亮導覽列；事件 scope 由頁內 chips 表示。"""
        if page_index == ANOMALY_MANAGEMENT_PAGE_INDEX:
            source_key = self._workbench_source_page_key
            if source_key in _QUEUE_PAGE_KEYS:
                self.sidebar.set_active(("page", source_key))
                return
            self.sidebar.set_active(("page", PAGE_EVENT_QUERY))
            return
        key = _PAGE_INDEX_TO_KEY.get(page_index)
        if key is not None:
            self.sidebar.set_active(("page", key))

    def _on_nav_activated(self, action) -> None:
        kind, value = action
        # 離開含未存資料的 NCR 頁面或供應商事件建立頁面前先確認（髒資料守衛）。
        stack = getattr(self, "stack", None)
        current = stack.currentIndex() if stack is not None else -1
        ncr = getattr(self, "ncr", None)
        if (
            ncr is not None
            and current >= 0
            and self._is_ncr_index(current)
            and self._action_target_index(action) != current
            and not ncr.confirm_can_leave(current - NCR_PAGE_OFFSET)
        ):
            return  # 取消導覽；側欄高亮未變更，無需還原。
        if (
            current in (VISIT_CREATE_PAGE_INDEX, ANOMALY_CREATE_PAGE_INDEX)
            and self._action_target_index(action) != current
        ):
            current_widget = stack.widget(current)
            if hasattr(current_widget, "can_leave") and not current_widget.can_leave():
                return
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
        elif kind == "command":
            if value == ACTION_OPEN_APPEARANCE_REDESIGN:
                self.open_appearance_preferences()

    def show_ncr_status(self, message: str, timeout_ms: int = 5000) -> None:
        """顯示 NCR 模組的狀態訊息（例如已建立不良單）於主視窗狀態列。"""
        self.statusBar().showMessage(message, timeout_ms)

    def open_appearance_preferences(self) -> None:
        from ui.widgets.appearance_preferences_dialog import AppearancePreferencesDialog
        dlg = AppearancePreferencesDialog(self)
        dlg.exec()

    def open_global_search(self) -> None:
        from ui.widgets.global_search_dialog import GlobalSearchDialog

        dialog = GlobalSearchDialog(self, self)
        dialog.exec()

    def findChild(self, arg__1: type, name: str = "", options: Any = None) -> Any:  # noqa: N802
        res = super().findChild(arg__1, name) if options is None else super().findChild(arg__1, name, options)
        if res is not None:
            return res
        for page_attr in ("_master_page", "_events_page", "_stats_page", "_ncr_stats_page", "_new_visit_page", "_new_anomaly_page"):
            page = getattr(self, page_attr, None)
            if isinstance(page, LazyPageWidget):
                child = page.findChild(arg__1, name, options)
                if child is not None:
                    return child
        return None

    def _open_master_data(self) -> None:
        self._switch_primary_page(MASTER_PAGE_INDEX)

    def open_master_supplier_search(self, supplier_name: str = "") -> None:
        self._open_master_data()
        master = self.master_widget
        if not supplier_name or not hasattr(master, "query_input"):
            return
        if hasattr(master, "tabs"):
            master.tabs.setCurrentIndex(0)
        master.query_input.setText(supplier_name)
        if hasattr(master, "_on_query_submitted"):
            master._on_query_submitted()

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
        # apply_quick_filters 更新了 scope；側欄維持事件管理頁高亮。
        self._sync_sidebar_active(EVENT_PAGE_INDEX)

    def open_anomaly_management(
        self,
        anomaly_id: str,
        *,
        edit: bool = False,
        source_page_key: str | None = None,
    ) -> None:
        """Open an anomaly in the main content area instead of a modal dialog."""
        if self._anomaly_management_page is None:
            return
        if source_page_key in _QUEUE_PAGE_KEYS:
            self._workbench_source_page_key = source_page_key
        elif source_page_key is None:
            current_key = _PAGE_INDEX_TO_KEY.get(self.stack.currentIndex())
            if current_key in _QUEUE_PAGE_KEYS:
                self._workbench_source_page_key = current_key
            else:
                self._workbench_source_page_key = None
        try:
            self._anomaly_management_page._source_scope = getattr(
                self.events_widget,
                "_filter_event_scope",
                repository.EVENT_SCOPE_ANOMALY_ONLY,
            ) or repository.EVENT_SCOPE_ANOMALY_ONLY
            self._anomaly_management_page.load_anomaly(anomaly_id, edit=edit)
        except Exception as exc:
            logger.exception("開啟異常管理頁失敗")
            QMessageBox.critical(self, "錯誤", f"開啟異常管理頁失敗：{exc}")
            return
        self._switch_primary_page(ANOMALY_MANAGEMENT_PAGE_INDEX)

    def open_supplier_360(self, supplier_id: str) -> None:
        if not supplier_id:
            return
        self._supplier_360_page.load_supplier(supplier_id)
        self._switch_primary_page(SUPPLIER_360_PAGE_INDEX)

    # ── Dialogs ─────────────────────────────────────────────────────────────

    def _ensure_has_active_suppliers(self) -> bool:
        may_proceed, should_warn = missing_supplier_create_gate(
            _product_service.has_active_suppliers()
        )
        if may_proceed:
            return True
        if should_warn:
            QMessageBox.warning(
                self,
                "需先建立供應商",
                "目前沒有可用供應商，請先到基礎資料建立供應商。",
            )
        else:
            logger.info(
                "目前沒有可用供應商；自動化環境略過提示對話框，改開基礎資料。"
            )
        self._open_master_data()
        return False

    def open_new_anomaly_create_page(self, initial_data: dict | None = None):
        if not self._ensure_has_active_suppliers():
            return
        if hasattr(self, "new_anomaly_page"):
            page = self.new_anomaly_page
            if initial_data and hasattr(page, "initial_data"):
                page.initial_data = dict(initial_data)
            if hasattr(page, "reset_form"):
                page.reset_form()
        self._switch_primary_page(ANOMALY_CREATE_PAGE_INDEX)

    def open_new_visit_create_page(self, initial_data: dict | None = None):
        if not self._ensure_has_active_suppliers():
            return
        if hasattr(self, "new_visit_page"):
            page = self.new_visit_page
            if initial_data and hasattr(page, "initial_data"):
                page.initial_data = dict(initial_data)
            if hasattr(page, "reset_form"):
                page.reset_form()
        self._switch_primary_page(VISIT_CREATE_PAGE_INDEX)

    def open_new_anomaly_dialog(self):
        self.open_new_anomaly_create_page()

    def open_new_visit_defect_dialog(self):
        self.open_new_visit_create_page()

    def open_new_visit_dialog(self):
        self.open_new_visit_create_page()

    def open_warehouse_nonconforming_tracker(self) -> None:
        """Compatibility route for older callers; opens the outsource pending line."""
        self.open_warehouse_pending_outsource()

    def open_warehouse_pending_outsource(self) -> None:
        """切換至嵌入式倉庫待處理委外加工頁（同一視窗內）。"""
        self._switch_primary_page(NCR_PENDING_OUTSOURCE_PAGE_INDEX)

    def open_warehouse_pending_material(self) -> None:
        """切換至嵌入式倉庫待處理原物料頁（同一視窗內）。"""
        self._switch_primary_page(NCR_PENDING_MATERIAL_PAGE_INDEX)

    def open_warehouse_history(self) -> None:
        """切換至嵌入式倉庫歷史紀錄頁（同一視窗內）。"""
        self._switch_primary_page(NCR_TRACE_PAGE_INDEX)

    def open_warehouse_unclassified_pending(self) -> None:
        """Open migrated warehouse records that still need a formal processing line."""
        ctrl = self._ensure_ncr_controller()
        if ctrl is None:
            QMessageBox.warning(self, "倉庫模組未載入", "目前無法開啟未分流待整理清單。")
            return
        from ncr.ui.defect_list import DefectListWidget as NcrDefectListWidget

        dialog = QDialog(self)
        dialog.setWindowTitle("未分流待整理")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(8, 12, 8, 8)
        widget = NcrDefectListWidget(
            ctrl.conn,
            dialog,
            workflow="tracking",
            processing_line=PROCESSING_LINE_UNCLASSIFIED,
        )
        widget.changed.connect(self.refresh_all_views)
        layout.addWidget(widget)
        dialog.resize(1100, 680)
        dialog.exec()
        # 整理後同步刷新倉庫清單頁(含待處理頁的未分流提示計數)與其餘 views。
        ctrl.refresh_all()

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
        self._supplier_overview_page.refresh_data()
        self._manager_view_page.refresh_data()
        self._event_overdue_queue_page.refresh_data()
        self._event_root_cause_queue_page.refresh_data()
        self._event_open_actions_queue_page.refresh_data()
        self._refresh_sidebar_badge()

    def open_manager_view(self) -> None:
        self._switch_primary_page(MANAGER_VIEW_PAGE_INDEX)

    def open_supplier_event_queue(self, page_key: str) -> None:
        page_index = _PAGE_KEY_TO_INDEX.get(page_key)
        if page_index is not None:
            self._switch_primary_page(page_index)

    def _refresh_sidebar_badge(self) -> None:
        try:
            summary = _query_service.get_dashboard_summary()
            count = int(summary.get("open_count", 0))
        except Exception:
            logger.exception("重新整理事件徽章失敗")
            count = 0
        self.sidebar.set_badge(("page", PAGE_EVENT_QUERY), count)
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
        try:
            from services import supplier_event_queue_service

            queue_counts = supplier_event_queue_service.get_supplier_event_queue_counts()
            self.sidebar.set_badge(
                ("page", PAGE_EVENT_OVERDUE),
                int(queue_counts.get("overdue_anomaly_count", 0)),
            )
            self.sidebar.set_badge(
                ("page", PAGE_EVENT_ROOT_CAUSE),
                int(queue_counts.get("root_cause_pending_count", 0)),
            )
            self.sidebar.set_badge(
                ("page", PAGE_EVENT_OPEN_ACTIONS),
                int(queue_counts.get("open_queue_action_count", 0)),
            )
        except Exception:
            logger.exception("重新整理供應商事件佇列徽章失敗")
            for page_key in _QUEUE_PAGE_KEYS:
                self.sidebar.set_badge(("page", page_key), 0)

    def _check_startup_unresolved(self) -> None:
        try:
            prefs = load_application_preferences()
            if prefs.auto_check_unresolved_on_startup:
                summary = _query_service.get_dashboard_summary()
                open_count = int(summary.get("open_anomalies_count", summary.get("standalone_open_count", 0)))
                if open_count > 0:
                    self.statusBar().showMessage(f"系統已就緒。目前共有 {open_count} 筆待處理之品質異常事件。", 8000)
                else:
                    self.statusBar().showMessage("系統已就緒。目前無待處理異常事件。", 5000)
        except Exception:
            logger.exception("啟動未結案檢查失敗")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):  # noqa: N802
        try:
            prefs = load_application_preferences()
        except Exception:
            logger.exception("讀取顯示偏好失敗，使用預設值")
            from ui.appearance_preferences import AppearancePreferences
            prefs = AppearancePreferences.default()
        is_automated = is_automated_runtime()

        if prefs.window_geometry_mode == "remember" and not is_automated:
            from PySide6.QtCore import QSettings
            settings = QSettings("Mitcorp", "SQEDailyWork")
            settings.setValue("main_window_geometry", self.saveGeometry())

        # NCR 嵌入頁有未存資料則攔截關閉；否則關閉共用 DB 連線。
        if self._ncr is not None:
            for local_index in range(NCR_PAGE_COUNT):
                if not self._ncr.confirm_can_leave(local_index):
                    event.ignore()
                    return
            self._ncr.close()
        is_interactive = self.isVisible() and not is_automated
        if prefs.auto_backup_prompt and is_interactive:
            reply = QMessageBox.question(
                self,
                "結束確認",
                "是否在結束工作前建立資料庫自動備份？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.StandardButton.Yes:

                try:
                    from database.connection import get_db_path
                    from database.backup import backup_sqlite_database, prune_backups
                    db_path = get_db_path()
                    if db_path.exists():
                        backup_dir = db_path.parent / "backups"
                        backup_dir.mkdir(parents=True, exist_ok=True)
                        from datetime import datetime
                        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        backup_file = backup_dir / f"sqe_auto_backup_{stamp}.db"
                        backup_sqlite_database(db_path, backup_file)
                        prune_backups(backup_dir, prefs.backup_retention_count, pattern="sqe_auto_backup_*.db")
                except Exception as exc:
                    logger.exception("關閉時自動備份失敗: %s", exc)

        if prefs.clean_temp_files_on_exit:
            try:
                import tempfile
                from pathlib import Path
                temp_dir = Path(tempfile.gettempdir())
                for pattern in ("sqe_*", "SQE_*", "event_report_*"):
                    for p in temp_dir.glob(pattern):
                        if p.is_file():
                            try:
                                p.unlink(missing_ok=True)
                            except Exception:
                                pass
            except Exception as exc:
                logger.exception("關閉時清理暫存檔失敗: %s", exc)


        event.accept()


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

