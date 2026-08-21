"""Dialog for maintaining the SMT process keyword preset library."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services.process_keyword_preset_service import (
    ProcessKeywordGroup,
    ProcessKeywordPresets,
    clone_presets,
    load_presets,
    save_presets,
)
from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    FORM_MAX_WIDTH,
    FORM_VERTICAL_SPACING,
    ROW_GAP,
)
from ui.window_sizing import fit_dialog_to_available_screen
from ui.widgets.common_widgets import DirtyTrackingMixin
from ui.widgets.defect_form_widgets import apply_dialog_layout, style_dialog_buttons


class _KeywordGroupEditor(QWidget):
    def __init__(self, group: ProcessKeywordGroup, parent=None):
        super().__init__(parent)
        self.group = group

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ROW_GAP)

        title = QLabel(group.label)
        title.setProperty("role", "sectionTitle")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.addItems(group.keywords)
        layout.addWidget(self.list_widget)

        button_row = QHBoxLayout()
        self.add_button = QPushButton("新增")
        self.add_button.setProperty("variant", "secondary")
        self.remove_button = QPushButton("刪除")
        self.remove_button.setProperty("variant", "dangerOutline")
        self.up_button = QPushButton("上移")
        self.up_button.setProperty("variant", "secondary")
        self.down_button = QPushButton("下移")
        self.down_button.setProperty("variant", "secondary")
        button_row.addWidget(self.add_button)
        button_row.addWidget(self.remove_button)
        button_row.addWidget(self.up_button)
        button_row.addWidget(self.down_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.add_button.clicked.connect(self._add_keyword)
        self.remove_button.clicked.connect(self._remove_selected)
        self.up_button.clicked.connect(self._move_up)
        self.down_button.clicked.connect(self._move_down)

    def keywords(self) -> list[str]:
        return [
            self.list_widget.item(index).text().strip()
            for index in range(self.list_widget.count())
            if self.list_widget.item(index).text().strip()
        ]

    def _add_keyword(self) -> None:
        text, ok = QInputDialog.getText(self, "新增關鍵詞", "關鍵詞：")
        if not ok:
            return
        keyword = text.strip()
        if not keyword:
            return
        existing = {self.list_widget.item(i).text().casefold() for i in range(self.list_widget.count())}
        if keyword.casefold() in existing:
            return
        self.list_widget.addItem(keyword)

    def _remove_selected(self) -> None:
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)

    def _move(self, delta: int) -> None:
        row = self.list_widget.currentRow()
        new_row = row + delta
        if row < 0 or new_row < 0 or new_row >= self.list_widget.count():
            return
        item = self.list_widget.takeItem(row)
        self.list_widget.insertItem(new_row, item)
        self.list_widget.setCurrentRow(new_row)

    def _move_up(self) -> None:
        self._move(-1)

    def _move_down(self) -> None:
        self._move(1)


class ProcessKeywordPresetsDialog(DirtyTrackingMixin, QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SMT 製程關鍵詞庫")
        self.setMinimumWidth(640)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        self._editors: list[_KeywordGroupEditor] = []
        self._baseline = clone_presets(load_presets())
        self._setup_ui()
        self._connect_dirty_signals()

    def _setup_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        content_layout.setSpacing(FORM_VERTICAL_SPACING)

        intro = QLabel(
            "維護供應商異常表單可選的 SMT 製程關鍵詞。使用者仍可在表單中輸入自訂詞。"
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "messageText")
        content_layout.addWidget(intro)

        for group in self._baseline.groups:
            box = QGroupBox(group.label)
            box_layout = QVBoxLayout(box)
            editor = _KeywordGroupEditor(group, box)
            box_layout.addWidget(editor)
            self._editors.append(editor)
            content_layout.addWidget(box)

        content_layout.addStretch(1)
        scroll.setWidget(content)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        style_dialog_buttons(buttons)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        apply_dialog_layout(self, scroll, buttons)
        fit_dialog_to_available_screen(self, maximum_width=FORM_MAX_WIDTH)

    def _connect_dirty_signals(self) -> None:
        signals = []
        for editor in self._editors:
            signals.extend(
                [
                    editor.add_button.clicked,
                    editor.remove_button.clicked,
                    editor.up_button.clicked,
                    editor.down_button.clicked,
                ]
            )
        self._init_dirty_tracking(signals)

    def _collect_presets(self) -> ProcessKeywordPresets:
        groups = [
            ProcessKeywordGroup(
                id=editor.group.id,
                label=editor.group.label,
                keywords=editor.keywords(),
            )
            for editor in self._editors
        ]
        return ProcessKeywordPresets(version=1, groups=groups)

    def _on_save(self) -> None:
        presets = self._collect_presets()
        if not any(group.keywords for group in presets.groups):
            QMessageBox.warning(self, "驗證失敗", "至少保留一個關鍵詞。")
            return
        try:
            save_presets(presets)
        except Exception as exc:
            QMessageBox.critical(self, "儲存失敗", str(exc))
            return
        self._baseline = clone_presets(presets)
        self._clear_dirty()
        self.accept()
