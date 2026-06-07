"""In-process embedding controller for the warehouse nonconforming-product module.

Hosts the consolidated DefectTrackerPage inside the SQE DailyWork main window's page stack.
"""
from __future__ import annotations

import sqlite3
from PySide6.QtCore import QObject
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QHBoxLayout, QPushButton, QWidget, QVBoxLayout, QTabWidget

from ncr.db.database import initialize_database
from ncr.ui.defect_form import DefectFormWidget
from ncr.ui.defect_list import DefectListWidget
from ncr.ui.ui_style import app_stylesheet

# Host page-stack offset: warehouse defect page sits after the three SQE DailyWork
# pages (首頁 / 事件管理 / 異常事件統計).
NCR_PAGE_OFFSET = 3
NCR_PAGE_SPECS: list[tuple[str, str, str]] = [
    ("不合格品追蹤", "倉庫不合格品追蹤", "倉庫實物不合格品管理與連續登錄"),
]
NCR_NAV_LABELS: list[str] = [spec[0] for spec in NCR_PAGE_SPECS]


class DefectTrackerPage(QWidget):
    """Consolidated Page for Defect Tracking, containing 3 tabs:
    1. 不合格品連續登錄 (DefectFormWidget)
    2. 待處理追蹤 (DefectListWidget in tracking workflow)
    3. 歷史紀錄 (DefectListWidget in trace workflow)
    """
    FORM_TAB_INDEX = 0

    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.conn = conn
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 0)
        layout.setSpacing(0)
        
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("defectTrackerTabs")
        
        self.list_widget = DefectListWidget(self.conn, workflow="tracking")
        self.trace_widget = DefectListWidget(self.conn, workflow="trace")
        self.form_widget = DefectFormWidget(self.conn)
        
        self.tabs.addTab(self.form_widget, "建立不合格品")
        self.tabs.addTab(self.list_widget, "待處理不合格品")
        self.tabs.addTab(self.trace_widget, "歷史紀錄")

        layout.addWidget(self.tabs)
        
        # Apply NCR specific QSS
        self.setStyleSheet(app_stylesheet())

    def refresh_all(self) -> None:
        self.form_widget.refresh_product_options()
        self.form_widget.refresh_supplier_options()
        self.list_widget.refresh_data()
        self.trace_widget.refresh_data()

    def open_create_entry(self) -> None:
        self.tabs.setCurrentIndex(self.FORM_TAB_INDEX)
        self.form_widget.focus_item_no()


class NcrController(QObject):
    """Owns the NCR DB connection and the single consolidated DefectTrackerPage."""

    def __init__(self, host_window: QObject, *, lazy_load: bool = False) -> None:
        super().__init__(host_window)
        self.host = host_window
        self.conn = initialize_database()

        self.tracker_page = DefectTrackerPage(self.conn)
        self._widgets = [self.tracker_page]

        # Cross-widget wiring.
        self.tracker_page.form_widget.saved.connect(self.refresh_all)
        self.tracker_page.form_widget.data_changed.connect(self.refresh_all)
        self.tracker_page.form_widget.status_message.connect(self._on_status_message)
        self.tracker_page.list_widget.changed.connect(self.refresh_all)
        self.tracker_page.trace_widget.changed.connect(self.refresh_all)

        self._has_loaded = False
        if not lazy_load:
            self.refresh_all()

    def pages(self) -> list[QWidget]:
        return list(self._widgets)

    def refresh_all(self) -> None:
        self._has_loaded = True
        self.tracker_page.refresh_all()
        # 同步重新整理 SQE DailyWork 的 views（例如首頁品質概況 KPI、統計分析等）
        refresh = getattr(self.host, "refresh_all_views", None)
        if callable(refresh):
            refresh()

    def refresh_for_local_index(self, local_index: int) -> None:
        # 單一頁面，直接 refresh_all
        self.refresh_all()

    def open_create_entry(self) -> None:
        self.tracker_page.open_create_entry()

    def confirm_can_leave(self, local_index: int) -> bool:
        """If DefectFormWidget is dirty, prompt user."""
        confirm = getattr(self.tracker_page.form_widget, "confirm_save_if_dirty", None)
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
            pass
