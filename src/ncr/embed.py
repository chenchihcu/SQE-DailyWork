"""In-process embedding controller for the warehouse nonconforming-product module.

Hosts the warehouse create, pending, and history pages inside the SQE DailyWork
main window's page stack.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ncr.db.database import initialize_database
from ncr.ui.defect_form import DefectFormWidget
from ncr.ui.defect_list import DefectListWidget
from ncr.ui.ui_style import app_stylesheet

# Host page-stack offset: warehouse defect page sits after the three SQE DailyWork
# pages (首頁 / 事件管理 / 異常事件統計).
NCR_PAGE_OFFSET = 3
NCR_PAGE_SPECS: list[tuple[str, str, str]] = [
    ("建立不合格品", "建立不合格品", "倉庫實物不合格品連續登錄"),
    ("待處理不合格品", "待處理不合格品", "未結案倉庫實物不合格品追蹤"),
    ("歷史紀錄", "歷史紀錄", "已結案倉庫實物不合格品查詢與溯源"),
]
NCR_NAV_LABELS: list[str] = [spec[0] for spec in NCR_PAGE_SPECS]


class NcrWorkflowPage(QWidget):
    """Tabless stack page wrapper for one warehouse nonconforming-product view."""

    def __init__(self, body: QWidget, object_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 0)
        layout.setSpacing(0)
        layout.addWidget(body)

        # Apply NCR specific QSS to each stack page.
        self.setStyleSheet(app_stylesheet())


class NcrController(QObject):
    """Owns the NCR DB connection and the three warehouse stack pages."""

    CREATE_PAGE_INDEX = 0
    PENDING_PAGE_INDEX = 1
    HISTORY_PAGE_INDEX = 2

    def __init__(self, host_window: QObject, *, lazy_load: bool = False) -> None:
        super().__init__(host_window)
        self.host = host_window
        self.conn = initialize_database()

        self.form_widget = DefectFormWidget(self.conn)
        self.list_widget = DefectListWidget(self.conn, workflow="tracking")
        self.trace_widget = DefectListWidget(self.conn, workflow="trace")

        self.create_page = NcrWorkflowPage(self.form_widget, "NcrCreatePage")
        self.pending_page = NcrWorkflowPage(self.list_widget, "NcrPendingPage")
        self.history_page = NcrWorkflowPage(self.trace_widget, "NcrHistoryPage")
        self._widgets = [self.create_page, self.pending_page, self.history_page]

        # Compatibility facade for tests or external callers that still access
        # the former consolidated page object.
        self.tracker_page = self.create_page
        self.tracker_page.FORM_TAB_INDEX = self.CREATE_PAGE_INDEX
        self.tracker_page.form_widget = self.form_widget
        self.tracker_page.list_widget = self.list_widget
        self.tracker_page.trace_widget = self.trace_widget
        self.tracker_page.open_create_entry = self.open_create_entry

        # Cross-widget wiring.
        self.form_widget.saved.connect(self.refresh_all)
        self.form_widget.data_changed.connect(self.refresh_all)
        self.form_widget.status_message.connect(self._on_status_message)
        self.list_widget.changed.connect(self.refresh_all)
        self.trace_widget.changed.connect(self.refresh_all)

        self._has_loaded = False
        if not lazy_load:
            self.refresh_all()

    def pages(self) -> list[QWidget]:
        return list(self._widgets)

    def refresh_all(self) -> None:
        self._has_loaded = True
        self.form_widget.refresh_product_options()
        self.form_widget.refresh_supplier_options()
        self.list_widget.refresh_data()
        self.trace_widget.refresh_data()
        # 同步重新整理 SQE DailyWork 的 views（例如首頁品質概況 KPI、統計分析等）
        refresh = getattr(self.host, "refresh_all_views", None)
        if callable(refresh):
            refresh()

    def refresh_for_local_index(self, local_index: int) -> None:
        # 三個一等側欄頁仍共用同一個倉庫工作流資料源；切換任一頁時同步刷新。
        self.refresh_all()

    def open_create_entry(self) -> None:
        self.form_widget.focus_item_no()

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
