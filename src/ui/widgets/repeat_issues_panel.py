"""Repeat issues panel for the anomaly workbench."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services import repeat_issue_service
from ui.layout_constants import FORM_VERTICAL_SPACING
from ui.widgets.common_widgets import EmptyStateWidget, create_section_card, style_table


class RepeatIssuesPanel(QWidget):
    """Show same-supplier similar historical anomalies for the active case."""

    open_anomaly_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._anomaly_id = ""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(FORM_VERTICAL_SPACING)

        self._card = create_section_card(self)
        card_layout = self._card.layout()
        assert card_layout is not None
        title = QLabel("潛在重複異常")
        title.setProperty("role", "sectionTitle")
        card_layout.addWidget(title)
        root.addWidget(self._card)

        self._hint = QLabel("同供應商的相似歷史案件")
        self._hint.setProperty("role", "muted")
        card_layout.addWidget(self._hint)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ("異常單號", "日期", "類別", "相似度", "比對原因", "狀態")
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        style_table(self._table)
        self._table.cellDoubleClicked.connect(self._on_row_activated)
        card_layout.addWidget(self._table)

        self._empty = EmptyStateWidget("無相似案件")
        self._empty.setVisible(False)
        card_layout.addWidget(self._empty)

    def load_anomaly(self, anomaly_id: str) -> None:
        self._anomaly_id = str(anomaly_id or "").strip()
        try:
            rows = (
                repeat_issue_service.list_repeat_issues(self._anomaly_id)
                if self._anomaly_id
                else []
            )
        except RuntimeError:
            rows = []
        self._table.setRowCount(0)
        has_rows = bool(rows)
        self._table.setVisible(has_rows)
        self._empty.setVisible(not has_rows)
        for row in rows:
            index = self._table.rowCount()
            self._table.insertRow(index)
            peer_id = str(row.get("peer_anomaly_id") or "")
            reasons = str(row.get("match_reasons") or "").replace("\n", "、")
            values = (
                row.get("anomaly_no") or "—",
                row.get("anomaly_date") or "—",
                row.get("category") or "—",
                str(row.get("similarity_score") or "—"),
                reasons or "—",
                row.get("status") or "—",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, peer_id)
                self._table.setItem(index, column, item)

    def _on_row_activated(self, row: int, _column: int) -> None:
        if row < 0:
            return
        item = self._table.item(row, 0)
        if item is None:
            return
        peer_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if peer_id:
            self.open_anomaly_requested.emit(peer_id)
