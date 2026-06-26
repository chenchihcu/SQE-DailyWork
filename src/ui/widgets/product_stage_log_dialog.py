from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    FORM_VERTICAL_SPACING,
    FORM_MAX_WIDTH,
)
from ui.widgets.common_widgets import (
    mark_button_variant,
    style_table,
)
from ui.window_sizing import fit_dialog_to_available_screen

logger = logging.getLogger(__name__)


class ProductStageLogDialog(QDialog):
    def __init__(self, product_label: str, logs: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("產品階段異動紀錄")
        self.setMinimumWidth(920)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        layout.setSpacing(FORM_VERTICAL_SPACING)
        header = QLabel(f"產品：{product_label}")
        header.setProperty("role", "helperText")
        layout.addWidget(header)
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(
            [
                "異動時間",
                "原階段",
                "新階段",
                "原因",
                "同步範圍",
                "異常更新筆數",
                "訪廠更新筆數",
                "操作者",
            ]
        )
        style_table(table)
        table.setRowCount(len(logs))
        for row_idx, row in enumerate(logs):
            table.setItem(row_idx, 0, QTableWidgetItem(str(row.get("changed_at") or "")))
            table.setItem(row_idx, 1, QTableWidgetItem(str(row.get("from_stage") or "")))
            table.setItem(row_idx, 2, QTableWidgetItem(str(row.get("to_stage") or "")))
            table.setItem(row_idx, 3, QTableWidgetItem(str(row.get("reason") or "")))
            table.setItem(row_idx, 4, QTableWidgetItem(str(row.get("sync_scope") or "")))
            table.setItem(
                row_idx, 5, QTableWidgetItem(str(int(row.get("anomalies_updated") or 0)))
            )
            table.setItem(row_idx, 6, QTableWidgetItem(str(int(row.get("visits_updated") or 0)))
            )
            table.setItem(row_idx, 7, QTableWidgetItem(str(row.get("changed_by") or "")))
        table.resizeColumnsToContents()
        layout.addWidget(table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        mark_button_variant(close_button, "secondary")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)
        fit_dialog_to_available_screen(self, preferred_width=960, preferred_height=620)
