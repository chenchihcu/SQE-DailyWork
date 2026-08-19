"""Complete an existing corrective action and append a matching audit entry.

Repository decides the next status (待有效性驗證 vs 已實施) based on whether
effectiveness verification is required.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
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

from services.event import _anomaly_workbench_service
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


class CompleteCorrectiveActionDialog(DirtyTrackingMixin, QDialog):
    """Mark a corrective action as completed with implementation evidence."""

    ca_completed = Signal(str)

    def __init__(
        self,
        corrective_action_id: str,
        description: str = "",
        *,
        verification_required: bool = False,
        parent=None,
        actor_name: str = "",
    ) -> None:
        super().__init__(parent)
        self._ca_id = (corrective_action_id or "").strip()
        if not self._ca_id:
            raise ValueError("Corrective action id is required")
        self._verification_required = bool(verification_required)
        self._actor_name = (actor_name or "").strip()
        self.setWindowTitle("完成改善措施")
        self.setModal(True)
        self.setMinimumWidth(WORKBENCH_DIALOG_MIN_WIDTH)
        self.setMaximumWidth(FORM_MAX_WIDTH)

        self.evidence_input = QTextEdit()
        self.evidence_input.setPlaceholderText(
            "填寫實施證據（照片說明、文件連結、實測數據等）"
        )
        self.evidence_input.setAcceptRichText(False)

        self._description = description

        self._setup_ui()
        self._update_validation()
        self._connect_dirty_signals()

    def _setup_ui(self) -> None:
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(*DIALOG_OUTER_MARGINS)
        lay.setSpacing(FORM_VERTICAL_SPACING)

        if self._description:
            ref = QLabel(f"措施內容：{self._description}")
            ref.setProperty("role", "helperText")
            ref.setWordWrap(True)
            lay.addWidget(ref)

        hint = QLabel(
            "送出後，狀態會自動推進為「待有效性驗證」；若措施未要求驗證，則直接轉為「已實施」。"
        )
        hint.setProperty("role", "helperText")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        form = QFormLayout()
        form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        form.addRow("實施證據", self.evidence_input)
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
            self._save_button.setText("標記完成")
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        apply_dialog_layout(self, scroll, buttons)

    def _connect_dirty_signals(self) -> None:
        self._init_dirty_tracking([
            self.evidence_input.textChanged,
        ])

    def _update_validation(self) -> None:
        if self._save_button is not None:
            self._save_button.setEnabled(True)
        if self._error_label is not None:
            self._error_label.setText("")

    def _on_submit(self) -> None:
        evidence = self.evidence_input.toPlainText().strip()
        try:
            _anomaly_workbench_service.record_ca_completion_with_audit(
                corrective_action_id=self._ca_id,
                implementation_evidence=evidence,
                actor_name=self._actor_name,
            )
        except ValueError as exc:
            set_field_invalid(self.evidence_input, True)
            if self._error_label is not None:
                self._error_label.setText(localize_exception(exc))
            return
        except Exception as exc:
            set_field_invalid(self.evidence_input, True)
            if self._error_label is not None:
                self._error_label.setText(
                    localize_popup_message(
                        f"完成改善措施失敗：{localize_exception(exc)}"
                    )
                )
            return
        self._dirty = False
        self.ca_completed.emit(self._ca_id)
        self.accept()
