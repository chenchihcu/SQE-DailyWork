"""In-process embedding controller for the warehouse nonconforming-product module.

Hosts the consolidated DefectTrackerPage inside the SQETOOL main window's page stack.
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

# Host page-stack offset: warehouse defect page sits after the six SQETOOL pages.
NCR_PAGE_OFFSET = 6
NCR_PAGE_SPECS: list[tuple[str, str, str]] = [
    ("不合格品追蹤", "倉庫不合格品追蹤", "倉庫實物不合格品管理與連續登錄"),
]
NCR_NAV_LABELS: list[str] = [spec[0] for spec in NCR_PAGE_SPECS]


class DefectTrackerPage(QWidget):
    """Consolidated Page for Defect Tracking, containing 3 tabs:
    1. 待處理追蹤 (DefectListWidget in tracking workflow)
    2. 結案與歷史溯源 (DefectListWidget in trace workflow)
    3. 不合格品連續登錄 (DefectFormWidget)
    """
    FORM_TAB_INDEX = 2

    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.conn = conn
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("defectTrackerTabs")
        
        self.list_widget = DefectListWidget(self.conn, workflow="tracking")
        self.trace_widget = DefectListWidget(self.conn, workflow="trace")
        self.form_widget = DefectFormWidget(self.conn)
        
        self.tabs.addTab(self.list_widget, "待處理不合格品")
        self.tabs.addTab(self.trace_widget, "結案與歷史溯源")
        self.tabs.addTab(self.form_widget, "建立不合格品")

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(22, 14, 22, 10)
        toolbar.setSpacing(12)

        self.source_label = QLabel("倉庫實物不合格品")
        self.source_label.setObjectName("NcrSourceTag")
        self.source_label.setProperty("role", "sourceTag")
        self.source_label.setToolTip("本頁只讀寫 defect_records 倉庫實物不合格品流程")
        toolbar.addWidget(self.source_label)
        toolbar.addStretch(1)

        self.create_button = QPushButton("建立不合格品")
        self.create_button.setObjectName("NcrCreateDefectButton")
        self.create_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.create_button.setToolTip("開啟不合格品建立欄位")
        self.create_button.clicked.connect(self.open_create_entry)
        toolbar.addWidget(self.create_button)

        self.tracking_button = QPushButton("待處理追蹤")
        self.tracking_button.setObjectName("NcrTrackingButton")
        self.tracking_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tracking_button.setToolTip("回到待處理不合格品清單")
        self.tracking_button.clicked.connect(lambda: self.tabs.setCurrentWidget(self.list_widget))
        toolbar.addWidget(self.tracking_button)
        self.tabs.currentChanged.connect(self._update_toolbar_state)
        
        layout.addLayout(toolbar)
        layout.addWidget(self.tabs)
        
        # Apply NCR specific QSS
        self.setStyleSheet(app_stylesheet())
        self._update_toolbar_state(self.tabs.currentIndex())

    def refresh_all(self) -> None:
        self.form_widget.refresh_product_options()
        self.form_widget.refresh_supplier_options()
        self.list_widget.refresh_data()
        self.trace_widget.refresh_data()

    def open_create_entry(self) -> None:
        self.tabs.setCurrentIndex(self.FORM_TAB_INDEX)
        self._update_toolbar_state(self.FORM_TAB_INDEX)
        self.form_widget.focus_item_no()

    def _update_toolbar_state(self, index: int) -> None:
        is_create_tab = index == self.FORM_TAB_INDEX
        is_tracking_tab = self.tabs.widget(index) is self.list_widget
        self.create_button.setVisible(not is_create_tab)
        self.create_button.setEnabled(not is_create_tab)
        self.tracking_button.setVisible(not is_tracking_tab)
        self.tracking_button.setEnabled(not is_tracking_tab)


class NcrController(QObject):
    """Owns the NCR DB connection and the single consolidated DefectTrackerPage."""

    def __init__(self, host_window: QObject) -> None:
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

        self.refresh_all()

    def pages(self) -> list[QWidget]:
        return list(self._widgets)

    def refresh_all(self) -> None:
        self.tracker_page.refresh_all()
        # 同步重新整理 SQETOOL 的 views（例如首頁品質概況 KPI、統計分析等）
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
        except Exception:
            pass
