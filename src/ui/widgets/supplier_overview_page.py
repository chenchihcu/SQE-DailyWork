from __future__ import annotations

import logging
from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services import supplier_360_service
from ui.list_column_contract import SUPPLIER_OVERVIEW_COLUMNS
from ui.layout_constants import (
    PAGE_OUTER_MARGINS,
    QUERY_WORKFLOW_PAGE_SPACING,
    SUPPLIER_OVERVIEW_ANOMALY_NO_WIDTH,
    SUPPLIER_OVERVIEW_CATEGORY_WIDTH,
    SUPPLIER_OVERVIEW_COUNT_WIDTH,
    SUPPLIER_OVERVIEW_DATE_WIDTH,
    SUPPLIER_OVERVIEW_DUE_DATE_WIDTH,
    SUPPLIER_OVERVIEW_NCR_WIDTH,
    SUPPLIER_OVERVIEW_STATUS_WIDTH,
    SUPPLIER_OVERVIEW_SUMMARY_WIDTH,
    SUPPLIER_OVERVIEW_SUPPLIER_WIDTH,
)
from ui.widgets.common_widgets import (
    QueryWorkflowShell,
    preserve_table_sorting,
    style_table,
)


logger = logging.getLogger(__name__)


class SupplierOverviewPage(QWidget):
    supplier_selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(*PAGE_OUTER_MARGINS)
        root.setSpacing(QUERY_WORKFLOW_PAGE_SPACING)

        controls = QueryWorkflowShell()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(12, 10, 12, 10)
        controls_layout.addWidget(QLabel("供應商總覽"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜尋供應商名稱")
        self.search.textChanged.connect(self._render)
        controls_layout.addWidget(self.search, 1)
        controls_layout.addWidget(QLabel("檢視範圍"))
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("有未結異常", "open_anomaly")
        self.scope_combo.addItem("有異常紀錄（含已結案）", "any_anomaly")
        self.scope_combo.addItem("全部供應商", "all")
        self.scope_combo.currentIndexChanged.connect(self.refresh_data)
        controls_layout.addWidget(self.scope_combo)
        refresh = QPushButton("重新整理")
        refresh.setProperty("variant", "secondary")
        refresh.clicked.connect(self.refresh_data)
        controls_layout.addWidget(refresh)
        root.addWidget(controls)

        self.table = QTableWidget(0, len(SUPPLIER_OVERVIEW_COLUMNS))
        self.table.setHorizontalHeaderLabels(
            [column.label for column in SUPPLIER_OVERVIEW_COLUMNS]
        )
        self.table.cellDoubleClicked.connect(self._open_row)
        style_table(self.table)
        for column, width in enumerate(
            (
                SUPPLIER_OVERVIEW_SUPPLIER_WIDTH,
                SUPPLIER_OVERVIEW_COUNT_WIDTH,
                SUPPLIER_OVERVIEW_COUNT_WIDTH,
                SUPPLIER_OVERVIEW_ANOMALY_NO_WIDTH,
                SUPPLIER_OVERVIEW_DATE_WIDTH,
                SUPPLIER_OVERVIEW_CATEGORY_WIDTH,
                SUPPLIER_OVERVIEW_SUMMARY_WIDTH,
                SUPPLIER_OVERVIEW_DUE_DATE_WIDTH,
                SUPPLIER_OVERVIEW_NCR_WIDTH,
                SUPPLIER_OVERVIEW_COUNT_WIDTH,
                SUPPLIER_OVERVIEW_STATUS_WIDTH,
            )
        ):
            self.table.setColumnWidth(column, width)
        root.addWidget(self.table, 1)
        self.refresh_data()

    def refresh_data(self) -> None:
        today = date.today()
        start_date = f"{today.year}-01-01"
        end_date = today.isoformat()
        try:
            self._rows = supplier_360_service.list_supplier_rows(
                view_scope=str(self.scope_combo.currentData() or "open_anomaly")
            )
            grades = supplier_360_service.list_supplier_scorecards(start_date, end_date)
            for row in self._rows:
                row["grade"] = grades.get(str(row.get("id") or ""), "—")
        except Exception:
            logger.exception(
                "供應商總覽查詢失敗 scope=%r",
                self.scope_combo.currentData(),
            )
            self._rows = []
        self._render()

    def _render(self) -> None:
        keyword = self.search.text().strip().lower()
        rows = [
            row for row in self._rows
            if not keyword or keyword in str(row.get("supplier_name") or "").lower()
        ]
        with preserve_table_sorting(self.table):
            self.table.setRowCount(0)
            for row in rows:
                index = self.table.rowCount()
                self.table.insertRow(index)
                values = (
                    row.get("supplier_name") or "—",
                    row.get("open_anomaly_count", 0),
                    row.get("overdue_anomaly_count", 0),
                    row.get("latest_anomaly_no") or "—",
                    row.get("latest_anomaly_date") or "—",
                    row.get("latest_anomaly_category") or "—",
                    row.get("latest_anomaly_desc") or "—",
                    row.get("latest_anomaly_due_date") or "—",
                    row.get("ncr_90d_count", 0),
                    row.get("grade") or "—",
                    "啟用" if row.get("is_active") else "停用",
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    if column == 0:
                        item.setData(32, str(row.get("id") or ""))
                    elif column == 6:
                        item.setToolTip(str(value))
                    self.table.setItem(index, column, item)

    def _open_row(self, row_index: int, _column: int) -> None:
        item = self.table.item(row_index, 0)
        if item is not None:
            self.supplier_selected.emit(str(item.data(32) or ""))
