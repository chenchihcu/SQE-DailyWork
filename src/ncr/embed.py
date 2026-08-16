"""In-process embedding controller for the warehouse nonconforming-product module.

Hosts the warehouse create, two processing-line pending pages, and history page
inside the SQE DailyWork main window's page stack.
"""
from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ncr.db.database import initialize_database
from ncr.models.defect import PROCESSING_LINE_MATERIAL, PROCESSING_LINE_OUTSOURCE
from ui.layout_constants import PAGE_OUTER_MARGINS

# Host page-stack offset: warehouse defect page sits after the three SQE DailyWork
# pages (首頁 / 事件管理 / 異常事件統計).
NCR_PAGE_OFFSET = 3
NCR_PAGE_SPECS: list[tuple[str, str, str]] = [
    ("建立不合格品", "建立不合格品", "倉庫實物不合格品連續登錄"),
    ("待處理委外加工", "待處理委外加工", "未結案委外加工倉庫實物不合格品追蹤"),
    ("待處理原物料", "待處理原物料", "未結案原物料倉庫實物不合格品追蹤"),
    ("歷史紀錄", "歷史紀錄", "已結案倉庫實物不合格品查詢與溯源"),
]
NCR_NAV_LABELS: list[str] = [spec[0] for spec in NCR_PAGE_SPECS]


class NcrWorkflowPage(QWidget):
    """Tabless stack page wrapper for one warehouse nonconforming-product view."""

    def __init__(
        self,
        body_or_factory: QWidget | Callable[[], QWidget],
        object_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self._factory = body_or_factory if callable(body_or_factory) else None
        self._body = body_or_factory if isinstance(body_or_factory, QWidget) else None

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(*PAGE_OUTER_MARGINS)
        self._layout.setSpacing(0)
        if self._body is not None:
            self._layout.addWidget(self._body)

    @property
    def body(self) -> QWidget:
        if self._body is None and self._factory is not None:
            self._body = self._factory()
            self._layout.addWidget(self._body)
        return self._body

    def ensure_widget(self) -> QWidget:
        return self.body

    def refresh_data(self) -> None:
        if self._body is not None and hasattr(self._body, "refresh_data"):
            self._body.refresh_data()

    def findChild(self, arg__1: type, name: str = "", options: Any = None) -> Any:  # noqa: N802
        self.ensure_widget()
        if options is not None:
            return super().findChild(arg__1, name, options)
        return super().findChild(arg__1, name)

    def findChildren(self, arg__1: type, *args: Any, **kwargs: Any) -> list:  # noqa: N802
        self.ensure_widget()
        return super().findChildren(arg__1, *args, **kwargs)


class NcrController(QObject):
    """Owns the NCR DB connection and the warehouse stack pages."""

    CREATE_PAGE_INDEX = 0
    PENDING_OUTSOURCE_PAGE_INDEX = 1
    PENDING_MATERIAL_PAGE_INDEX = 2
    HISTORY_PAGE_INDEX = 3

    def __init__(self, host_window: QObject, *, lazy_load: bool = False) -> None:
        super().__init__(host_window)
        self.host = host_window
        self.conn = initialize_database()
        self._lazy_load = lazy_load

        def _create_form():
            from ncr.ui.defect_form import DefectFormWidget
            w = DefectFormWidget(self.conn, lazy_load=lazy_load)
            w.saved.connect(self.refresh_all)
            w.data_changed.connect(self.refresh_all)
            w.status_message.connect(self._on_status_message)
            return w

        def _create_pending_outsource():
            from ncr.ui.defect_list import DefectListWidget
            w = DefectListWidget(
                self.conn,
                workflow="tracking",
                processing_line=PROCESSING_LINE_OUTSOURCE,
                lazy_load=lazy_load,
            )
            w.changed.connect(self.refresh_all)
            w.unclassified_link_requested.connect(self._open_unclassified_cleanup)
            return w

        def _create_pending_material():
            from ncr.ui.defect_list import DefectListWidget
            w = DefectListWidget(
                self.conn,
                workflow="tracking",
                processing_line=PROCESSING_LINE_MATERIAL,
                lazy_load=lazy_load,
            )
            w.changed.connect(self.refresh_all)
            w.unclassified_link_requested.connect(self._open_unclassified_cleanup)
            return w

        def _create_trace():
            from ncr.ui.defect_list import DefectListWidget
            w = DefectListWidget(
                self.conn,
                workflow="trace",
                lazy_load=lazy_load,
            )
            w.changed.connect(self.refresh_all)
            return w

        self.create_page = NcrWorkflowPage(_create_form, "NcrCreatePage")
        self.pending_outsource_page = NcrWorkflowPage(_create_pending_outsource, "NcrPendingOutsourcePage")
        self.pending_material_page = NcrWorkflowPage(_create_pending_material, "NcrPendingMaterialPage")
        self.history_page = NcrWorkflowPage(_create_trace, "NcrHistoryPage")

        self._widgets = [
            self.create_page,
            self.pending_outsource_page,
            self.pending_material_page,
            self.history_page,
        ]

        # Compatibility facade for tests or external callers that still access
        # the former consolidated page object.
        self.tracker_page = self.create_page
        self.tracker_page.FORM_TAB_INDEX = self.CREATE_PAGE_INDEX
        self.tracker_page.open_create_entry = self.open_create_entry

        self._has_loaded = False
        if not lazy_load:
            self.refresh_all()

    @property
    def form_widget(self):
        return self.create_page.body

    @form_widget.setter
    def form_widget(self, value):
        self.create_page._body = value

    @property
    def pending_outsource_widget(self):
        return self.pending_outsource_page.body

    @pending_outsource_widget.setter
    def pending_outsource_widget(self, value):
        self.pending_outsource_page._body = value

    @property
    def pending_material_widget(self):
        return self.pending_material_page.body

    @pending_material_widget.setter
    def pending_material_widget(self, value):
        self.pending_material_page._body = value

    @property
    def trace_widget(self):
        return self.history_page.body

    @trace_widget.setter
    def trace_widget(self, value):
        self.history_page._body = value

    @property
    def list_widget(self):
        return self.pending_outsource_widget

    def pages(self) -> list[QWidget]:
        return list(self._widgets)

    def refresh_all(self) -> None:
        self._has_loaded = True
        self.form_widget.refresh_product_options()
        self.form_widget.refresh_supplier_options()
        self.pending_outsource_widget.refresh_data()
        self.pending_material_widget.refresh_data()
        self.trace_widget.refresh_data()
        # 同步重新整理 SQE DailyWork 的 views（例如首頁品質概況 KPI、統計分析等）
        refresh = getattr(self.host, "refresh_all_views", None)
        if callable(refresh):
            refresh()

    def refresh_for_local_index(self, local_index: int) -> None:
        # 按需刷新當前分頁，避免切換單一頁面時重複全量查詢其餘未載入頁面。
        if local_index == self.CREATE_PAGE_INDEX:
            self.form_widget.refresh_product_options()
            self.form_widget.refresh_supplier_options()
        elif local_index == self.PENDING_OUTSOURCE_PAGE_INDEX:
            self.pending_outsource_widget.refresh_data()
        elif local_index == self.PENDING_MATERIAL_PAGE_INDEX:
            self.pending_material_widget.refresh_data()
        elif local_index == self.HISTORY_PAGE_INDEX:
            self.trace_widget.refresh_data()
        else:
            self.refresh_all()

    def open_create_entry(self) -> None:
        self.form_widget.focus_item_no()

    def _open_unclassified_cleanup(self) -> None:
        """Route the pending-page unclassified link to the host cleanup dialog."""
        opener = getattr(self.host, "open_warehouse_unclassified_pending", None)
        if callable(opener):
            opener()

    def confirm_can_leave(self, local_index: int) -> bool:
        """Prompt before leaving the create page when the form is dirty."""
        if local_index != self.CREATE_PAGE_INDEX:
            return True
        confirm = getattr(self.form_widget, "confirm_save_if_dirty", None)
        if callable(confirm) and not confirm():
            return False
        return True

    def _on_status_message(self, message: str, timeout_ms: int = 5000) -> None:
        notify = getattr(self.host, "show_ncr_status", None)
        if callable(notify):
            notify(message, timeout_ms)

    def close(self) -> None:
        try:
            self.conn.close()
        except sqlite3.Error:
            logger.exception("Failed to close NCR DB connection")
