from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database.connection import get_connection
from ncr.models.defect import (
    PROCESSING_LINE_MATERIAL,
    PROCESSING_LINE_OUTSOURCE,
    PROCESSING_LINE_UNCLASSIFIED,
)
from ncr.services import stats_service as warehouse_stats_service
from services import supplier_event_queue_service
from ui.layout_constants import CONTROL_ROW_SPACING, PANEL_MARGINS, ROOT_SECTION_SPACING
from ui.sidebar_nav import (
    PAGE_EVENT_OPEN_ACTIONS,
    PAGE_EVENT_OVERDUE,
    PAGE_EVENT_ROOT_CAUSE,
)
from ui.widgets.common_widgets import BrandDivider

logger = logging.getLogger(__name__)


class HomeWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._queue_buttons: dict[str, QPushButton] = {}
        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(ROOT_SECTION_SPACING)
        root.addWidget(self._build_hub_panel(), 1)

    def _build_hub_panel(self) -> QFrame:
        panel = QFrame()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(*PANEL_MARGINS)
        outer.setSpacing(CONTROL_ROW_SPACING)

        title = QLabel("供應商事件作業佇列")
        title.setProperty("role", "sectionTitle")
        outer.addWidget(title)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.addStretch(1)
        manager_view_button = QPushButton("主管檢視 →")
        manager_view_button.setProperty("variant", "secondary")
        manager_view_button.setCursor(Qt.CursorShape.PointingHandCursor)
        manager_view_button.setToolTip("開啟案件總覽（含已結案與品質欄位）")
        manager_view_button.clicked.connect(self._open_manager_view)
        title_row.addWidget(manager_view_button)
        outer.addLayout(title_row)
        outer.addWidget(BrandDivider())

        queue_row = QHBoxLayout()
        queue_row.setContentsMargins(0, 0, 0, 0)
        queue_row.setSpacing(CONTROL_ROW_SPACING)
        queue_specs = (
            ("HomeQueueOverdueLink", "逾期未結：— 件　→", PAGE_EVENT_OVERDUE, "icons/anomaly.svg"),
            ("HomeQueueRootCauseLink", "待根本原因：— 件　→", PAGE_EVENT_ROOT_CAUSE, None),
            ("HomeQueueOpenActionsLink", "進行中處置：— 筆　→", PAGE_EVENT_OPEN_ACTIONS, None),
        )
        for object_name, placeholder, page_key, _icon in queue_specs:
            button = QPushButton(placeholder)
            button.setObjectName(object_name)
            button.setProperty("variant", "secondary")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda _checked=False, key=page_key: self._open_queue(key)
            )
            self._queue_buttons[page_key] = button
            queue_row.addWidget(button, 1)
        outer.addLayout(queue_row)

        warehouse_title = QLabel("倉庫不合格品")
        warehouse_title.setProperty("role", "sectionTitle")
        outer.addWidget(warehouse_title)
        outer.addWidget(BrandDivider())

        shortcut_row = QHBoxLayout()
        shortcut_row.setContentsMargins(0, 0, 0, 0)
        shortcut_row.setSpacing(CONTROL_ROW_SPACING)
        self._warehouse_outsource_btn = self._make_warehouse_shortcut(
            "HomeBacklogWarehouseOutsourceLink",
            "委外待處理：— 件　→",
            "開啟同一視窗內的待處理委外加工清單",
            "open_warehouse_pending_outsource",
        )
        self._warehouse_material_btn = self._make_warehouse_shortcut(
            "HomeBacklogWarehouseMaterialLink",
            "原物料待處理：— 件　→",
            "開啟同一視窗內的待處理原物料清單",
            "open_warehouse_pending_material",
        )
        self._warehouse_unclassified_btn = self._make_warehouse_shortcut(
            "HomeBacklogWarehouseUnclassifiedLink",
            "未分流待整理：— 件　→",
            "開啟既有未分流資料整理清單",
            "open_warehouse_unclassified_pending",
        )
        for button in (
            self._warehouse_outsource_btn,
            self._warehouse_material_btn,
            self._warehouse_unclassified_btn,
        ):
            shortcut_row.addWidget(button, 1)
        outer.addLayout(shortcut_row)
        outer.addStretch(1)
        return panel

    def _make_warehouse_shortcut(
        self,
        object_name: str,
        text: str,
        tooltip: str,
        method_name: str,
    ) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(object_name)
        button.setProperty("variant", "secondary")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tooltip)
        button.clicked.connect(
            lambda _checked=False, name=method_name: self._invoke_main(name)
        )
        return button

    def _invoke_main(self, method_name: str) -> None:
        callback = getattr(self.main_window, method_name, None)
        if callable(callback):
            callback()

    def _open_manager_view(self) -> None:
        self._invoke_main("open_manager_view")

    def _open_queue(self, page_key: str) -> None:
        opener = getattr(self.main_window, "open_supplier_event_queue", None)
        if callable(opener):
            opener(page_key)

    def refresh_data(self) -> None:
        pending_counts = {
            PROCESSING_LINE_OUTSOURCE: 0,
            PROCESSING_LINE_MATERIAL: 0,
            PROCESSING_LINE_UNCLASSIFIED: 0,
        }
        try:
            with get_connection() as conn:
                pending_counts = (
                    warehouse_stats_service.get_pending_counts_by_processing_line(conn)
                )
        except Exception:
            logger.exception("讀取不合格品統計失敗")
            if hasattr(self.main_window, "statusBar"):
                self.main_window.statusBar().showMessage(
                    "讀取倉庫待處理統計失敗，請檢查資料庫連線。",
                    8000,
                )

        try:
            queue_counts = supplier_event_queue_service.get_supplier_event_queue_counts()
            self._queue_buttons[PAGE_EVENT_OVERDUE].setText(
                f"逾期未結：{int(queue_counts.get('overdue_anomaly_count', 0))} 件　→"
            )
            self._queue_buttons[PAGE_EVENT_ROOT_CAUSE].setText(
                f"待根本原因：{int(queue_counts.get('root_cause_pending_count', 0))} 件　→"
            )
            self._queue_buttons[PAGE_EVENT_OPEN_ACTIONS].setText(
                f"進行中處置：{int(queue_counts.get('open_queue_action_count', 0))} 筆　→"
            )
        except Exception:
            logger.exception("讀取供應商事件佇列統計失敗")
            if hasattr(self.main_window, "statusBar"):
                self.main_window.statusBar().showMessage(
                    "讀取供應商事件佇列統計失敗，請檢查資料庫連線。",
                    8000,
                )

        self._warehouse_outsource_btn.setText(
            f"委外待處理：{int(pending_counts.get(PROCESSING_LINE_OUTSOURCE, 0))} 件　→"
        )
        self._warehouse_material_btn.setText(
            f"原物料待處理：{int(pending_counts.get(PROCESSING_LINE_MATERIAL, 0))} 件　→"
        )
        self._warehouse_unclassified_btn.setText(
            f"未分流待整理：{int(pending_counts.get(PROCESSING_LINE_UNCLASSIFIED, 0))} 件　→"
        )
