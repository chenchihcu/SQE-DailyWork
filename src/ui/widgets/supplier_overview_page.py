from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services import supplier_360_service
from ui.widgets.common_widgets import QueryWorkflowShell, style_table


class SupplierOverviewPage(QWidget):
    supplier_selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(10)

        controls = QueryWorkflowShell()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(12, 10, 12, 10)
        controls_layout.addWidget(QLabel("供應商總覽"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜尋供應商名稱")
        self.search.textChanged.connect(self._render)
        controls_layout.addWidget(self.search, 1)
        refresh = QPushButton("重新整理")
        refresh.setProperty("variant", "secondary")
        refresh.clicked.connect(self.refresh_data)
        controls_layout.addWidget(refresh)
        root.addWidget(controls)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["供應商", "未結異常", "逾期", "近 90 日 NCR", "最近訪廠", "狀態"]
        )
        self.table.cellDoubleClicked.connect(self._open_row)
        style_table(self.table)
        root.addWidget(self.table, 1)
        self.refresh_data()

    def refresh_data(self) -> None:
        try:
            self._rows = supplier_360_service.list_supplier_rows()
        except Exception:
            self._rows = []
        self._render()

    def _render(self) -> None:
        keyword = self.search.text().strip().lower()
        rows = [
            row for row in self._rows
            if not keyword or keyword in str(row.get("supplier_name") or "").lower()
        ]
        self.table.setRowCount(0)
        for row in rows:
            index = self.table.rowCount()
            self.table.insertRow(index)
            values = (
                row.get("supplier_name") or "—",
                row.get("open_anomaly_count", 0),
                row.get("overdue_anomaly_count", 0),
                row.get("ncr_90d_count", 0),
                row.get("latest_visit_date") or "—",
                "啟用" if row.get("is_active") else "停用",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(32, str(row.get("id") or ""))
                self.table.setItem(index, column, item)

    def _open_row(self, row_index: int, _column: int) -> None:
        item = self.table.item(row_index, 0)
        if item is not None:
            self.supplier_selected.emit(str(item.data(32) or ""))
