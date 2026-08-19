"""Complete / cancel an existing next-action row from the anomaly workbench.

Single dialog with a completion-or-cancel toggle so the workbench can expose
both state transitions without two dialogs. Repository validation stays the
authority (open → 已完成 / 已取消 only).
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from ui.layout_constants import WORKBENCH_DIALOG_MIN_WIDTH

from services.event import _anomaly_action_service
from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    FORM_HORIZONTAL_SPACING,
    FORM_MAX_WIDTH,
    FORM_VERTICAL_SPACING,
)
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.widgets.common_widgets import (
    DirtyTrackingMixin,
    make_inline_error_label,
    set_field_invalid,
)
from ui.widgets.defect_form_widgets import (
    apply_dialog_layout,
    style_dialog_buttons,
)

OUTCOME_COMPLETED = "已完成"
OUTCOME_CANCELLED = "已取消"
OUTCOME_OPTIONS = [
    (OUTCOME_COMPLETED, "標記為已完成"),
    (OUTCOME_CANCELLED, "標記為已取消"),
]


class CompleteActionDialog(DirtyTrackingMixin, QDialog):
    """Toggle an open next-action to 已完成 or 已取消 with a note."""

    action_updated = Signal(str)

    def __init__(
        self,
        action_id: str,
        action_summary: str = "",
        parent=None,
        *,
        actor_name: str = "",
    ) -> None:
        super().__init__(parent)
        self._action_id = (action_id or "").strip()
        if not self._action_id:
            raise ValueError("Action id is required")
        self._actor_name = (actor_name or "").strip()
        self.setWindowTitle("更新處置狀態")
        self.setModal(True)
        self.setMinimumWidth(WORKBENCH_DIALOG_MIN_WIDTH)
        self.setMaximumWidth(FORM_MAX_WIDTH)

        self.outcome_combo = QComboBox()
        for value, label in OUTCOME_OPTIONS:
            self.outcome_combo.addItem(label, value)
        self.outcome_combo.setCurrentIndex(0)

        self.note_input = QTextEdit()
        self.note_input.setPlaceholderText(
            "完成說明／取消原因（選填；儲存後將寫入處理歷程）"
        )
        self.note_input.setAcceptRichText(False)

        self._action_summary = action_summary

        self._setup_ui()
        self._update_validation()
        self._connect_dirty_signals()

    def _setup_ui(self) -> None:
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(*DIALOG_OUTER_MARGINS)
        lay.setSpacing(FORM_VERTICAL_SPACING)

        if self._action_summary:
            ref = QLabel(f"處置內容：{self._action_summary}")
            ref.setProperty("role", "helperText")
            ref.setWordWrap(True)
            lay.addWidget(ref)

        form = QFormLayout()
        form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        form.addRow("狀態結果", self.outcome_combo)
        form.addRow("說明", self.note_input)
        self._error_label = make_inline_error_label()
        form.addRow("", self._error_label)
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
            self._save_button.setText("更新狀態")
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        apply_dialog_layout(self, scroll, buttons)

    def _connect_dirty_signals(self) -> None:
        self._init_dirty_tracking([
            self.outcome_combo.currentIndexChanged,
            self.note_input.textChanged,
        ])

    def _update_validation(self) -> None:
        if self._save_button is not None:
            self._save_button.setEnabled(True)
        if self._error_label is not None:
            self._error_label.setText("")

    def _on_submit(self) -> None:
        outcome = str(self.outcome_combo.currentData() or OUTCOME_COMPLETED)
        note = self.note_input.toPlainText().strip()
        try:
            if outcome == OUTCOME_CANCELLED:
                _anomaly_action_service.cancel_action(
                    self._action_id,
                    cancel_note=note,
                    actor_name=self._actor_name,
                )
            else:
                _anomaly_action_service.complete_action(
                    self._action_id,
                    completion_note=note,
                    actor_name=self._actor_name,
                )
        except ValueError as exc:
            set_field_invalid(self.note_input, True)
            if self._error_label is not None:
                self._error_label.setText(localize_exception(exc))
            return
        except Exception as exc:
            set_field_invalid(self.note_input, True)
            if self._error_label is not None:
                self._error_label.setText(
                    localize_popup_message(
                        f"更新處置失敗：{localize_exception(exc)}"
                    )
                )
            return
        self._dirty = False
        self.action_updated.emit(self._action_id)
        self.accept()
