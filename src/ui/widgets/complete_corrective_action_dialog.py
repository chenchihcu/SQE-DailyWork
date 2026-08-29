"""Complete a canonical improvement Action and record implementation details."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from ui.layout_constants import WORKBENCH_DIALOG_MIN_WIDTH

from services.event import _case_action_service
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
        action_id: str,
        description: str = "",
        *,
        verification_required: bool = False,
        parent=None,
        actor_name: str = "",
    ) -> None:
        super().__init__(parent)
        self._action_id = (action_id or "").strip()
        if not self._action_id:
            raise ValueError("Action id is required")
        self._verification_required = bool(verification_required)
        self._actor_name = (actor_name or "").strip()
        self.setWindowTitle("完成改善措施")
        self.setModal(True)
        self.setMinimumWidth(WORKBENCH_DIALOG_MIN_WIDTH)
        self.setMaximumWidth(FORM_MAX_WIDTH)

        self.evidence_input = BulletListWidget(
            placeholder="填寫實施證據（照片說明、文件連結、實測數據等）"
        )
        self.note_input = BulletListWidget(placeholder="完成說明（選填）")

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
            "送出後執行狀態固定為「已完成」；有效性狀態會依是否需要驗證另行推導。"
        )
        hint.setProperty("role", "helperText")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        form = QFormLayout()
        form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        form.addRow("實施證據", self.evidence_input)
        form.addRow("完成說明", self.note_input)
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
            self.evidence_input.valueChanged,
            self.note_input.valueChanged,
        ])

    def _update_validation(self) -> None:
        if self._save_button is not None:
            self._save_button.setEnabled(True)
        if self._error_label is not None:
            self._error_label.setText("")

    def _on_submit(self) -> None:
        evidence = self.evidence_input.get_formatted_text().strip()
        try:
            _case_action_service.complete_case_action(
                self._action_id,
                implementation_evidence=evidence,
                completion_note=self.note_input.get_formatted_text().strip(),
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
        self.ca_completed.emit(self._action_id)
        self.accept()
