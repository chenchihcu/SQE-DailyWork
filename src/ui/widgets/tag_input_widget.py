"""Multi-select tag input for SMT process keywords."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.process_keyword_codec import (
    MAX_PROCESS_KEYWORDS_PER_ANOMALY,
    parse_process_keywords,
    serialize_process_keywords,
)
from services.process_keyword_preset_service import all_suggestion_keywords
from ui.layout_constants import INLINE_SPACING


class TagInputWidget(QWidget):
    """Chip-based multi keyword picker with editable combo suggestions."""

    valueChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tags: list[str] = []
        self._read_only = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(INLINE_SPACING)

        self._chips_host = QWidget()
        self._chips_layout = QVBoxLayout(self._chips_host)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(4)
        root.addWidget(self._chips_host)

        input_row = QWidget()
        input_layout = QHBoxLayout(input_row)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(INLINE_SPACING)

        self._combo = QComboBox()
        self._combo.setEditable(True)
        self._combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._combo.setMaxVisibleItems(16)
        self._combo.setAccessibleName("SMT 製程關鍵詞")
        self._combo.setToolTip("從詞庫選取或直接輸入自訂關鍵詞")
        line_edit = self._combo.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText("選取或輸入關鍵詞")
            line_edit.setClearButtonEnabled(True)
            line_edit.returnPressed.connect(self._add_current_text)
        self._combo.setMinimumWidth(0)
        self._combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._add_button = QPushButton("加入")
        self._add_button.setProperty("variant", "secondary")
        self._add_button.setAccessibleName("加入 SMT 製程關鍵詞")
        self._add_button.clicked.connect(self._add_current_text)

        input_layout.addWidget(self._combo, 1)
        input_layout.addWidget(self._add_button)
        root.addWidget(input_row)

        self._input_row = input_row
        self.reload_suggestions()

    def reload_suggestions(self) -> None:
        current = self._combo.currentText()
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItems(all_suggestion_keywords())
        self._combo.setCurrentText(current)
        self._combo.blockSignals(False)

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = bool(read_only)
        self._input_row.setVisible(not self._read_only)
        self._rebuild_chips()

    def tags(self) -> list[str]:
        return list(self._tags)

    def get_delimited_text(self) -> str:
        return serialize_process_keywords(self._tags)

    def set_delimited_text(self, value: object) -> None:
        self._tags = parse_process_keywords(value)
        self._rebuild_chips()
        self.valueChanged.emit()

    def _add_current_text(self) -> None:
        if self._read_only:
            return
        text = self._combo.currentText().strip()
        if not text:
            return
        existing = {item.casefold() for item in self._tags}
        if text.casefold() in existing:
            self._combo.setCurrentText("")
            return
        if len(self._tags) >= MAX_PROCESS_KEYWORDS_PER_ANOMALY:
            return
        self._tags.append(text)
        self._combo.setCurrentText("")
        self._rebuild_chips()
        self.valueChanged.emit()

    def _remove_tag(self, keyword: str) -> None:
        if self._read_only:
            return
        target = keyword.casefold()
        self._tags = [item for item in self._tags if item.casefold() != target]
        self._rebuild_chips()
        self.valueChanged.emit()

    def _rebuild_chips(self) -> None:
        while self._chips_layout.count():
            item = self._chips_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self._tags:
            return

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row_host = QWidget()
        row_host.setLayout(row)

        used = 0
        for keyword in self._tags:
            chip = QPushButton(keyword)
            chip.setObjectName("ProcessKeywordChip")
            chip.setProperty("role", "scopeChip")
            chip.setCursor(
                Qt.CursorShape.ArrowCursor if self._read_only else Qt.CursorShape.PointingHandCursor
            )
            chip.setToolTip("點擊移除" if not self._read_only else keyword)
            if not self._read_only:
                chip.clicked.connect(lambda _checked=False, value=keyword: self._remove_tag(value))
            row.addWidget(chip)
            used += 1
            if used % 6 == 0:
                row.addStretch(1)
                self._chips_layout.addWidget(row_host)
                row_host = QWidget()
                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(4)
                row_host.setLayout(row)

        row.addStretch(1)
        self._chips_layout.addWidget(row_host)
