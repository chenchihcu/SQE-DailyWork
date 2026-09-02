"""Dialog for maintaining the anomaly source preset library."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
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

from services.anomaly_source_preset_service import (
    AnomalySourceEntry,
    AnomalySourcePresets,
    clone_sources,
    count_anomalies_using_source,
    load_sources,
    new_custom_source_id,
    save_sources,
    validate_sources,
)
from services.anomaly_trace_contract import TRACE_FIELD_LABELS
from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    FORM_MAX_WIDTH,
    FORM_VERTICAL_SPACING,
    GRID_GUTTER,
    ROW_GAP,
)
from ui.window_sizing import fit_dialog_to_available_screen
from ui.widgets.common_widgets import DirtyTrackingMixin
from ui.widgets.defect_form_widgets import apply_dialog_layout, style_dialog_buttons


class AnomalySourcePresetsDialog(DirtyTrackingMixin, QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("異常來源辭庫")
        self.setMinimumWidth(720)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        self._baseline = clone_sources(load_sources())
        self._entries = [clone_sources(self._baseline).sources[i] for i in range(len(self._baseline.sources))]
        self._visible_checks: dict[str, QCheckBox] = {}
        self._required_checks: dict[str, QCheckBox] = {}
        self._setup_ui()
        self._connect_dirty_signals()
        if self._source_list.count() > 0:
            self._source_list.setCurrentRow(0)

    def _setup_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        content_layout.setSpacing(FORM_VERTICAL_SPACING)

        intro = QLabel(
            "維護供應商異常表單可選的異常來源，並設定各來源對應的 ERP 追溯單號顯示與必填規則。"
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "messageText")
        content_layout.addWidget(intro)

        body = QHBoxLayout()
        body.setSpacing(GRID_GUTTER)

        left_col = QVBoxLayout()
        left_col.setSpacing(ROW_GAP)
        left_col.addWidget(QLabel("來源清單"))
        self._source_list = QListWidget()
        self._source_list.addItems(entry.label for entry in self._entries)
        self._source_list.currentRowChanged.connect(self._on_source_selected)
        left_col.addWidget(self._source_list)

        list_buttons = QHBoxLayout()
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
            list_buttons.addWidget(button)
        list_buttons.addStretch(1)
        left_col.addLayout(list_buttons)
        body.addLayout(left_col, 1)

        right_col = QVBoxLayout()
        right_col.setSpacing(ROW_GAP)
        editor_group = QGroupBox("來源設定")
        editor_layout = QVBoxLayout(editor_group)
        editor_layout.setSpacing(ROW_GAP)

        editor_layout.addWidget(QLabel("來源名稱"))
        self._label_input = QLineEdit()
        self._label_input.setAccessibleName("異常來源名稱")
        self._label_input.textChanged.connect(self._sync_current_entry_from_editor)
        editor_layout.addWidget(self._label_input)

        trace_group = QGroupBox("ERP 追溯單號欄位")
        trace_layout = QGridLayout(trace_group)
        trace_layout.setHorizontalSpacing(GRID_GUTTER)
        trace_layout.setVerticalSpacing(ROW_GAP)
        trace_layout.addWidget(QLabel("欄位"), 0, 0)
        trace_layout.addWidget(QLabel("顯示"), 0, 1)
        trace_layout.addWidget(QLabel("必填"), 0, 2)
        for row_index, (field_key, field_label) in enumerate(TRACE_FIELD_LABELS.items(), start=1):
            trace_layout.addWidget(QLabel(field_label), row_index, 0)
            visible_check = QCheckBox()
            visible_check.setAccessibleName(f"{field_label} 顯示")
            required_check = QCheckBox()
            required_check.setAccessibleName(f"{field_label} 必填")
            visible_check.toggled.connect(self._on_visible_toggled)
            required_check.toggled.connect(self._sync_current_entry_from_editor)
            visible_check.toggled.connect(self._sync_current_entry_from_editor)
            self._visible_checks[field_key] = visible_check
            self._required_checks[field_key] = required_check
            trace_layout.addWidget(visible_check, row_index, 1)
            trace_layout.addWidget(required_check, row_index, 2)
        editor_layout.addWidget(trace_group)
        right_col.addWidget(editor_group)
        body.addLayout(right_col, 2)
        content_layout.addLayout(body)

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

        self._add_button.clicked.connect(self._add_source)
        self._remove_button.clicked.connect(self._remove_source)
        self._up_button.clicked.connect(lambda: self._move_source(-1))
        self._down_button.clicked.connect(lambda: self._move_source(1))

    def _connect_dirty_signals(self) -> None:
        signals = [
            self._add_button.clicked,
            self._remove_button.clicked,
            self._up_button.clicked,
            self._down_button.clicked,
            self._label_input.textChanged,
        ]
        for check in self._visible_checks.values():
            signals.append(check.toggled)
        for check in self._required_checks.values():
            signals.append(check.toggled)
        self._init_dirty_tracking(signals)

    def _current_row(self) -> int:
        return self._source_list.currentRow()

    def _current_entry(self) -> AnomalySourceEntry | None:
        row = self._current_row()
        if row < 0 or row >= len(self._entries):
            return None
        return self._entries[row]

    def _on_source_selected(self, row: int) -> None:
        entry = self._entries[row] if 0 <= row < len(self._entries) else None
        self._label_input.blockSignals(True)
        self._label_input.setText(entry.label if entry else "")
        self._label_input.blockSignals(False)
        for field_key, visible_check in self._visible_checks.items():
            required_check = self._required_checks[field_key]
            visible_check.blockSignals(True)
            required_check.blockSignals(True)
            is_visible = field_key in (entry.visible_trace_fields if entry else [])
            is_required = field_key in (entry.required_trace_fields if entry else [])
            visible_check.setChecked(is_visible)
            required_check.setChecked(is_required)
            required_check.setEnabled(is_visible)
            visible_check.blockSignals(False)
            required_check.blockSignals(False)
        self._label_input.setEnabled(entry is not None)
        for check in self._visible_checks.values():
            check.setEnabled(entry is not None)
        for field_key, check in self._required_checks.items():
            check.setEnabled(
                entry is not None and self._visible_checks[field_key].isChecked()
            )

    def _on_visible_toggled(self, checked: bool) -> None:
        for field_key, visible_check in self._visible_checks.items():
            required_check = self._required_checks[field_key]
            if visible_check is self.sender():
                if not checked:
                    required_check.setChecked(False)
                required_check.setEnabled(checked)
                break
        self._sync_current_entry_from_editor()

    def _sync_current_entry_from_editor(self, *_args) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        entry.label = self._label_input.text().strip()
        visible_fields: list[str] = []
        required_fields: list[str] = []
        for field_key, visible_check in self._visible_checks.items():
            if visible_check.isChecked():
                visible_fields.append(field_key)
                if self._required_checks[field_key].isChecked():
                    required_fields.append(field_key)
        entry.visible_trace_fields = visible_fields
        entry.required_trace_fields = required_fields
        row = self._current_row()
        if 0 <= row < self._source_list.count():
            self._source_list.item(row).setText(entry.label or "(未命名)")

    def _add_source(self) -> None:
        self._sync_current_entry_from_editor()
        entry = AnomalySourceEntry(
            id=new_custom_source_id(),
            label="新異常來源",
            visible_trace_fields=[],
            required_trace_fields=[],
        )
        self._entries.append(entry)
        self._source_list.addItem(entry.label)
        self._source_list.setCurrentRow(self._source_list.count() - 1)

    def _remove_source(self) -> None:
        row = self._current_row()
        entry = self._current_entry()
        if row < 0 or entry is None:
            return
        usage_count = count_anomalies_using_source(entry.label)
        if usage_count > 0:
            QMessageBox.warning(
                self,
                "無法刪除",
                f"異常來源「{entry.label}」已有 {usage_count} 筆事件使用，無法刪除。",
            )
            return
        confirm = QMessageBox.question(
            self,
            "確認刪除",
            f"確定要刪除異常來源「{entry.label}」？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._entries.pop(row)
        self._source_list.takeItem(row)
        if self._source_list.count() > 0:
            self._source_list.setCurrentRow(min(row, self._source_list.count() - 1))
        else:
            self._on_source_selected(-1)

    def _move_source(self, delta: int) -> None:
        row = self._current_row()
        new_row = row + delta
        if row < 0 or new_row < 0 or new_row >= len(self._entries):
            return
        self._sync_current_entry_from_editor()
        self._entries[row], self._entries[new_row] = self._entries[new_row], self._entries[row]
        item = self._source_list.takeItem(row)
        self._source_list.insertItem(new_row, item)
        self._source_list.setCurrentRow(new_row)

    def _collect_presets(self) -> AnomalySourcePresets:
        self._sync_current_entry_from_editor()
        return AnomalySourcePresets(version=1, sources=clone_sources(AnomalySourcePresets(version=1, sources=self._entries)).sources)

    def _on_save(self) -> None:
        presets = self._collect_presets()
        validation_error = validate_sources(presets)
        if validation_error:
            QMessageBox.warning(self, "驗證失敗", validation_error)
            return
        try:
            save_sources(presets)
        except Exception as exc:
            QMessageBox.critical(self, "儲存失敗", str(exc))
            return
        self._baseline = clone_sources(presets)
        self._entries = list(self._baseline.sources)
        self._clear_dirty()
        self.accept()
