"""Dynamic bullet list widget for structured item entry in SQE DailyWork forms."""

from __future__ import annotations

import re
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class BulletListItemRow(QWidget):
    """Single row in the bullet list widget."""

    valueChanged = Signal()
    removeRequested = Signal(object)

    def __init__(self, index: int = 1, text: str = "", parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 2, 0, 2)
        self.layout.setSpacing(6)

        self.num_label = QLabel(f"{index}.")
        self.num_label.setFixedWidth(28)
        self.num_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.num_label.setProperty("uiRole", "bulletIndexLabel")

        self.line_edit = QLineEdit(text)
        self.line_edit.setPlaceholderText(f"條目 {index}")
        self.line_edit.textChanged.connect(self._on_text_changed)

        self.btn_delete = QPushButton("刪除")
        self.btn_delete.setFixedWidth(48)
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.setProperty("variant", "dangerOutline")
        self.btn_delete.clicked.connect(lambda: self.removeRequested.emit(self))

        self.layout.addWidget(self.num_label)
        self.layout.addWidget(self.line_edit, 1)
        self.layout.addWidget(self.btn_delete)

    def _on_text_changed(self):
        self.valueChanged.emit()

    def set_index(self, index: int):
        self.num_label.setText(f"{index}.")
        self.line_edit.setPlaceholderText(f"條目 {index}")

    def text(self) -> str:
        return self.line_edit.text().strip()

    def set_text(self, text: str):
        self.line_edit.setText(text)


class BulletListWidget(QWidget):
    """Widget allowing dynamic addition, deletion, and auto-numbering of items."""

    valueChanged = Signal()

    def __init__(self, placeholder: str = "新增條目...", parent=None):
        super().__init__(parent)
        self._rows: list[BulletListItemRow] = []
        self._placeholder = placeholder

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(4)

        self.items_container = QWidget()
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(4)
        self.main_layout.addWidget(self.items_container)

        self.btn_add = QPushButton("+ 新增條目")
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.setProperty("variant", "dashedPrimary")
        self.btn_add.clicked.connect(lambda: self.add_item(""))
        self.main_layout.addWidget(self.btn_add)

        # Always start with at least 1 empty row
        self.add_item("")

    def add_item(self, text: str = "") -> BulletListItemRow:
        index = len(self._rows) + 1
        row = BulletListItemRow(index=index, text=text, parent=self)
        row.valueChanged.connect(self._on_row_value_changed)
        row.removeRequested.connect(self._remove_row)
        self._rows.append(row)
        self.items_layout.addWidget(row)
        self._update_indices()
        self.valueChanged.emit()
        return row

    def _remove_row(self, row: BulletListItemRow):
        if len(self._rows) <= 1:
            row.set_text("")
            self.valueChanged.emit()
            return

        if row in self._rows:
            self._rows.remove(row)
            self.items_layout.removeWidget(row)
            row.deleteLater()
            self._update_indices()
            self.valueChanged.emit()

    def _update_indices(self):
        for idx, row in enumerate(self._rows, start=1):
            row.set_index(idx)

    def _on_row_value_changed(self):
        self.valueChanged.emit()

    def get_items(self) -> list[str]:
        items = [row.text() for row in self._rows if row.text()]
        return items

    def set_items(self, items: list[str]):
        for row in list(self._rows):
            self.items_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        if not items:
            self.add_item("")
        else:
            for item_text in items:
                self.add_item(item_text)
        self.valueChanged.emit()

    def get_formatted_text(self) -> str:
        items = self.get_items()
        if not items:
            return ""
        return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))

    def set_formatted_text(self, text: str):
        if not text or not text.strip():
            self.set_items([])
            return

        lines = text.strip().splitlines()
        extracted_items = []
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            cleaned = re.sub(r"^(\d+[\.\)]|\-|•|\*)\s*", "", line_str)
            extracted_items.append(cleaned if cleaned else line_str)

        self.set_items(extracted_items)

    def setReadOnly(self, read_only: bool):
        self.btn_add.setVisible(not read_only)
        for row in self._rows:
            row.line_edit.setReadOnly(read_only)
            row.btn_delete.setVisible(not read_only)

    def setPlainText(self, text: str):
        """Compatibility alias for QTextEdit.setPlainText."""
        self.set_formatted_text(text)

    def toPlainText(self) -> str:
        """Compatibility alias for QTextEdit.toPlainText."""
        return self.get_formatted_text()

