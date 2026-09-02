"""Dialog for maintaining the anomaly category preset library."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services.anomaly_category_preset_service import (
    AnomalyCategoryPresets,
    clone_categories,
    count_anomalies_using_category,
    load_categories,
    save_categories,
    validate_categories,
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


class AnomalyCategoryPresetsDialog(DirtyTrackingMixin, QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("異常類別辭庫")
        self.setMinimumWidth(560)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        self._baseline = clone_categories(load_categories())
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
            "維護供應商異常表單可選的異常類別。表單僅能從此辭庫選取，不可手動輸入自訂值。"
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "messageText")
        content_layout.addWidget(intro)

        content_layout.addWidget(QLabel("類別清單"))
        self._list_widget = QListWidget()
        self._list_widget.addItems(self._baseline.categories)
        content_layout.addWidget(self._list_widget)

        button_row = QHBoxLayout()
        self._add_button = QPushButton("新增")
        self._add_button.setProperty("variant", "secondary")
        self._remove_button = QPushButton("刪除")
        self._remove_button.setProperty("variant", "dangerOutline")
        self._up_button = QPushButton("上移")
        self._up_button.setProperty("variant", "secondary")
        self._down_button = QPushButton("下移")
        self._down_button.setProperty("variant", "secondary")
        for button in (
            self._add_button,
            self._remove_button,
            self._up_button,
            self._down_button,
        ):
            button_row.addWidget(button)
        button_row.addStretch(1)
        content_layout.addLayout(button_row)
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

        self._add_button.clicked.connect(self._add_category)
        self._remove_button.clicked.connect(self._remove_category)
        self._up_button.clicked.connect(lambda: self._move(-1))
        self._down_button.clicked.connect(lambda: self._move(1))

    def _connect_dirty_signals(self) -> None:
        self._init_dirty_tracking(
            [
                self._add_button.clicked,
                self._remove_button.clicked,
                self._up_button.clicked,
                self._down_button.clicked,
            ]
        )

    def _categories(self) -> list[str]:
        return [
            self._list_widget.item(index).text().strip()
            for index in range(self._list_widget.count())
            if self._list_widget.item(index).text().strip()
        ]

    def _add_category(self) -> None:
        text, ok = QInputDialog.getText(self, "新增異常類別", "類別名稱：")
        if not ok:
            return
        category = text.strip()
        if not category:
            return
        existing = {self._list_widget.item(i).text().casefold() for i in range(self._list_widget.count())}
        if category.casefold() in existing:
            QMessageBox.warning(self, "驗證失敗", f"異常類別「{category}」已存在。")
            return
        self._list_widget.addItem(category)

    def _remove_category(self) -> None:
        row = self._list_widget.currentRow()
        if row < 0:
            return
        category = self._list_widget.item(row).text().strip()
        usage_count = count_anomalies_using_category(category)
        if usage_count > 0:
            QMessageBox.warning(
                self,
                "無法刪除",
                f"異常類別「{category}」已有 {usage_count} 筆事件使用，無法刪除。",
            )
            return
        confirm = QMessageBox.question(
            self,
            "確認刪除",
            f"確定要刪除異常類別「{category}」？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._list_widget.takeItem(row)

    def _move(self, delta: int) -> None:
        row = self._list_widget.currentRow()
        new_row = row + delta
        if row < 0 or new_row < 0 or new_row >= self._list_widget.count():
            return
        item = self._list_widget.takeItem(row)
        self._list_widget.insertItem(new_row, item)
        self._list_widget.setCurrentRow(new_row)

    def _collect_presets(self) -> AnomalyCategoryPresets:
        return AnomalyCategoryPresets(version=1, categories=self._categories())

    def _on_save(self) -> None:
        presets = self._collect_presets()
        validation_error = validate_categories(presets)
        if validation_error:
            QMessageBox.warning(self, "驗證失敗", validation_error)
            return
        try:
            save_categories(presets)
        except Exception as exc:
            QMessageBox.critical(self, "儲存失敗", str(exc))
            return
        self._baseline = clone_categories(presets)
        self._clear_dirty()
        self.accept()
