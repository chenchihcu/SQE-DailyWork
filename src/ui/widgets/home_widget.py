from __future__ import annotations

import logging

from PySide6.QtCore import QDate, Qt

logger = logging.getLogger(__name__)
from PySide6.QtWidgets import (
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database import repository
from database.connection import get_connection
from ncr.models.defect import (
    PROCESSING_LINE_MATERIAL,
    PROCESSING_LINE_OUTSOURCE,
    PROCESSING_LINE_UNCLASSIFIED,
)
from ncr.services import stats_service as warehouse_stats_service
from services.event import _query_service as event_service
from ui.layout_constants import (
    BACKLOG_SUPPLIER_MAX_COL_WIDTH,
    PANEL_MARGINS,
    ROOT_SECTION_SPACING,
)
from ui.widgets.common_widgets import (
    BrandDivider,
    EmptyStateWidget,
    SortableTableWidgetItem,
    apply_table_action_affordance,
    create_status_item,
    preserve_table_sorting,
    style_table,
    text_table_item,
)


class HomeWidget(QWidget):
    # Daily-cockpit backlog list size (read-only actionable to-do list).
    _BACKLOG_LIMIT = 8

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._backlog_rows: list[dict] = []
        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(ROOT_SECTION_SPACING)

        # Daily-cockpit backlog: read-only actionable to-do list that fills the
        # first screen. Reads existing services only; rows route through existing
        # navigation (no new write paths).
        root.addWidget(self._build_backlog_panel(), 1)

    def _build_backlog_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("HomeBacklogPanel")
        panel.setProperty("role", "panel")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(*PANEL_MARGINS)
        outer.setSpacing(8)

        self._backlog_title = QLabel("待辦事項（待處理異常，逾期優先）")
        self._backlog_title.setProperty("role", "sectionTitle")
        outer.addWidget(self._backlog_title)
        outer.addWidget(BrandDivider())

        self._backlog_table = QTableWidget()
        self._backlog_table.setObjectName("HomeBacklogTable")
        self._backlog_table.setColumnCount(4)
        self._backlog_table.setHorizontalHeaderLabels(
            ["異常單號", "供應商", "問題/摘要", "狀態"]
        )
        style_table(self._backlog_table)
        apply_table_action_affordance(
            self._backlog_table,
            "點擊待辦列開啟事件管理頁，並帶入該供應商的待處理異常篩選",
        )
        header = self._backlog_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._backlog_table.cellClicked.connect(self._on_backlog_row_clicked)
        outer.addWidget(self._backlog_table, 1)

        self._backlog_empty = EmptyStateWidget(
            "目前沒有待處理異常",
            "本月供應商異常均已結案，或尚無待處理項目。",
            parent=self,
        )
        self._backlog_empty.setVisible(False)
        outer.addWidget(self._backlog_empty)

        # 倉庫待處理正式雙入口：兩條處理線各自導向對應頁；未分流作為整理入口。
        shortcut_row = QHBoxLayout()
        shortcut_row.setContentsMargins(0, 0, 0, 0)
        shortcut_row.setSpacing(8)
        self._warehouse_outsource_btn = self._make_warehouse_shortcut(
            "HomeBacklogWarehouseOutsourceLink",
            "待處理委外加工：— 件　→",
            "開啟同一視窗內的待處理委外加工清單",
            "open_warehouse_pending_outsource",
        )
        self._warehouse_material_btn = self._make_warehouse_shortcut(
            "HomeBacklogWarehouseMaterialLink",
            "待處理原物料：— 件　→",
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

    def _month_key(self) -> str:
        return QDate.currentDate().toString("yyyyMM")

    def refresh_data(self):
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

        self._refresh_backlog(pending_counts)

    def _refresh_backlog(self, pending_counts: dict[str, int]) -> None:
        """Populate the read-only backlog list from existing services only."""
        try:
            overdue_rows = event_service.list_events(
                {"event_type": "ANOMALY", "status": "待處理", "overdue_only": True}
            )
        except Exception:
            logger.exception("讀取逾期待辦清單失敗")
            overdue_rows = []
        try:
            pending_rows = event_service.list_events(
                {"event_type": "ANOMALY", "status": "待處理"}
            )
        except Exception:
            logger.exception("讀取待辦清單失敗")
            pending_rows = []

        # 逾期優先，再補其餘待處理；以 event_id 去重。
        merged: list[dict] = []
        seen: set[str] = set()
        for row in [*overdue_rows, *pending_rows]:
            event_id = row.get("event_id") or row.get("anomaly_id")
            key = str(event_id or f"{row.get('supplier_name','')}_{row.get('event_date','')}_{row.get('content','')}")
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)

        self._render_backlog_rows(merged[: self._BACKLOG_LIMIT])

        self._warehouse_outsource_btn.setText(
            f"待處理委外加工：{int(pending_counts.get(PROCESSING_LINE_OUTSOURCE, 0))} 件　→"
        )
        self._warehouse_material_btn.setText(
            f"待處理原物料：{int(pending_counts.get(PROCESSING_LINE_MATERIAL, 0))} 件　→"
        )
        self._warehouse_unclassified_btn.setText(
            f"未分流待整理：{int(pending_counts.get(PROCESSING_LINE_UNCLASSIFIED, 0))} 件　→"
        )

    def _render_backlog_rows(self, rows: list[dict]) -> None:
        self._backlog_rows = list(rows)
        has_rows = bool(rows)
        self._backlog_table.setVisible(has_rows)
        self._backlog_empty.setVisible(not has_rows)

        with preserve_table_sorting(self._backlog_table):
            self._backlog_table.setRowCount(0)
            for idx, row in enumerate(rows):
                self._backlog_table.insertRow(idx)
                no_val = row.get("ref_no") or row.get("event_date") or "—"
                no_item = SortableTableWidgetItem(str(no_val), sort_key=str(no_val))
                no_item.setData(Qt.ItemDataRole.UserRole, dict(row))
                self._backlog_table.setItem(idx, 0, no_item)
                full_name = str(row.get("supplier_name") or "—")
                name_item = text_table_item(full_name)
                name_item.setToolTip(full_name)
                self._backlog_table.setItem(idx, 1, name_item)
                content_str = str(row.get("content") or "—")
                self._backlog_table.setItem(idx, 2, text_table_item(content_str))
                status_str = str(row.get("status") or "待處理")
                self._backlog_table.setItem(
                    idx, 3, create_status_item(status_str, sort_key=status_str)
                )

        # Cap supplier column so very long names don't crowd the problem/summary column.
        actual_w = self._backlog_table.horizontalHeader().sectionSize(1)
        if actual_w > BACKLOG_SUPPLIER_MAX_COL_WIDTH:
            self._backlog_table.setColumnWidth(1, BACKLOG_SUPPLIER_MAX_COL_WIDTH)

    def _on_backlog_row_clicked(self, row_idx: int, _column_idx: int) -> None:
        item = self._backlog_table.item(row_idx, 0)
        if item is None:
            return
        payload = item.data(Qt.ItemDataRole.UserRole)
        supplier = (
            str(payload.get("supplier_name") or "") if isinstance(payload, dict) else ""
        )
        open_filters = getattr(self.main_window, "open_event_query_with_filters", None)
        if not callable(open_filters):
            return
        open_filters(
            event_type="ANOMALY",
            supplier_keyword=supplier,
            yyyymm=self._month_key(),
            status="待處理",
            event_scope=repository.EVENT_SCOPE_ANOMALY_ONLY,
        )
