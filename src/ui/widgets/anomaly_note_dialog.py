"""Minimal analysis-note create dialog for the anomaly case-workbench.

Adds one FACT / INFERENCE / ASSUMPTION / UNKNOWN note to an anomaly. Shared
dialog-footer + required-field validation only; author and evidence handling
stay in the service.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from ui.layout_constants import WORKBENCH_DIALOG_WIDE_MIN_WIDTH

from database.repo_helpers import ANOMALY_EVIDENCE_LABELS, ANOMALY_EVIDENCE_TYPES
from services.event import _anomaly_workbench_service
from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    FORM_HORIZONTAL_SPACING,
    FORM_MAX_WIDTH,
    FORM_VERTICAL_SPACING,
)
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.widgets.bullet_list_widget import BulletListWidget
from ui.widgets.common_widgets import (
    DirtyTrackingMixin,
    RequiredFieldLabel,
    make_inline_error_label,
    set_field_invalid,
)
from ui.widgets.defect_form_widgets import (
    apply_dialog_layout,
    style_dialog_buttons,
)


class AnomalyNoteDialog(DirtyTrackingMixin, QDialog):
    """Create a single analysis note on an anomaly."""

    note_created = Signal(str)

    def __init__(self, anomaly_id: str, parent=None) -> None:
        super().__init__(parent)
        self._anomaly_id = anomaly_id.strip()
        self.setWindowTitle("新增分析紀錄")
        self.setModal(True)
        self.setMinimumWidth(WORKBENCH_DIALOG_WIDE_MIN_WIDTH)
        self.setMaximumWidth(FORM_MAX_WIDTH)

        self.content_input = BulletListWidget(
            placeholder="記錄已確認事實、推論、假設或待確認事項"
        )

        self.evidence_combo = QComboBox()
        for value in ANOMALY_EVIDENCE_TYPES:
            label = ANOMALY_EVIDENCE_LABELS[value]
            self.evidence_combo.addItem(f"{label}（{value}）", value)
        self.evidence_combo.setCurrentIndex(0)

        self._setup_ui()
        self._update_validation()
        self._connect_dirty_signals()

    def _setup_ui(self) -> None:
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(*DIALOG_OUTER_MARGINS)
        lay.setSpacing(FORM_VERTICAL_SPACING)

        form = QFormLayout()
        form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        form.addRow(RequiredFieldLabel("新增紀錄"), self.content_input)
        self._error_label = make_inline_error_label()
        form.addRow("", self._error_label)
        form.addRow("證據分類", self.evidence_combo)
        lay.addLayout(form)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self._save_button = style_dialog_buttons(buttons)
        if self._save_button:
            self._save_button.setText("新增紀錄")
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        apply_dialog_layout(self, scroll, buttons)
        self.content_input.valueChanged.connect(self._update_validation)

    def _connect_dirty_signals(self) -> None:
        self._init_dirty_tracking([
            self.content_input.valueChanged,
            self.evidence_combo.currentIndexChanged,
        ])

    @property
    def _has_content(self) -> bool:
        return bool(self.content_input.get_formatted_text().strip())

    def _update_validation(self) -> None:
        valid = self._has_content
        set_field_invalid(self.content_input, not valid)
        if self._error_label is not None:
            self._error_label.setText("" if valid else "請輸入分析紀錄內容（必填）")
        if self._save_button is not None:
            self._save_button.setEnabled(valid)

    def _on_submit(self) -> None:
        content = self.content_input.get_formatted_text().strip()
        if not content:
            self._update_validation()
            return
        evidence = str(self.evidence_combo.currentData() or "UNKNOWN")
        try:
            note_id = _anomaly_workbench_service.create_analysis_note(
                anomaly_id=self._anomaly_id,
                content=content,
                evidence_type=evidence,
            )
        except ValueError as exc:
            set_field_invalid(self.content_input, True)
            if self._error_label is not None:
                self._error_label.setText(localize_exception(exc))
            return
        except Exception as exc:
            set_field_invalid(self.content_input, True)
            if self._error_label is not None:
                self._error_label.setText(
                    localize_popup_message(f"新增紀錄失敗：{localize_exception(exc)}")
                )
            return
        self._dirty = False
        self.note_created.emit(note_id)
        self.accept()
