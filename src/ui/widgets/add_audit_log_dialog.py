"""Add a free-form audit log entry from the anomaly workbench."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
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
    RequiredFieldLabel,
    make_inline_error_label,
    set_field_invalid,
)
from ui.widgets.defect_form_widgets import (
    apply_dialog_layout,
    style_dialog_buttons,
)


# Predefined action kinds cover the most common workbench annotations; free-form
# text input remains available via the combo's `setEditable(True)` UI affordance.
ACTION_KIND_OPTIONS = [
    "NOTE",
    "MEETING",
    "SUPPLIER_RESPONSE",
    "INTERNAL_REVIEW",
    "CUSTOMER_NOTIFY",
    "OTHER",
]


class AddAuditLogDialog(DirtyTrackingMixin, QDialog):
    """Append a free-form audit entry that surfaces on the workbench timeline."""

    audit_created = Signal(str)

    def __init__(
        self,
        anomaly_id: str,
        parent=None,
        *,
        actor_name: str = "",
    ) -> None:
        super().__init__(parent)
        self._anomaly_id = (anomaly_id or "").strip()
        if not self._anomaly_id:
            raise ValueError("Anomaly id is required")
        self._actor_name = (actor_name or "").strip()
        self.setWindowTitle("新增處理紀錄")
        self.setModal(True)
        self.setMinimumWidth(WORKBENCH_DIALOG_MIN_WIDTH)
        self.setMaximumWidth(FORM_MAX_WIDTH)

        self.action_combo = QComboBox()
        for kind in ACTION_KIND_OPTIONS:
            self.action_combo.addItem(kind, kind)
        self.action_combo.setEditable(True)
        self.action_combo.setCurrentIndex(0)

        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText(
            "紀錄內容（會出現在處理歷程；建議簡要描述事件、決定或追蹤事項）"
        )
        self.message_input.setAcceptRichText(False)

        self._setup_ui()
        self._update_validation()
        self._connect_dirty_signals()

    def _setup_ui(self) -> None:
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(*DIALOG_OUTER_MARGINS)
        lay.setSpacing(FORM_VERTICAL_SPACING)

        hint = QLabel(
            "送出後將以 append-only 形式寫入處理歷程。建議優先使用對應的工作台按鈕"
            "（處置、改善、8D 審查…）；此處僅供補充事件、會議或臨時註記。"
        )
        hint.setProperty("role", "helperText")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        form = QFormLayout()
        form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        form.addRow(RequiredFieldLabel("事件類型"), self.action_combo)
        form.addRow(RequiredFieldLabel("紀錄內容"), self.message_input)
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
            self._save_button.setText("新增紀錄")
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        apply_dialog_layout(self, scroll, buttons)

        self.action_combo.currentTextChanged.connect(self._update_validation)
        self.message_input.textChanged.connect(self._update_validation)

    def _connect_dirty_signals(self) -> None:
        self._init_dirty_tracking([
            self.action_combo.currentTextChanged,
            self.message_input.textChanged,
        ])

    def _update_validation(self) -> None:
        action_text = self.action_combo.currentText().strip()
        message_text = self.message_input.toPlainText().strip()
        valid = bool(action_text) and bool(message_text)
        set_field_invalid(self.action_combo, not action_text)
        set_field_invalid(self.message_input, not message_text)
        if self._error_label is not None:
            if not action_text and not message_text:
                self._error_label.setText("請輸入事件類型與紀錄內容")
            elif not action_text:
                self._error_label.setText("請輸入事件類型（必填）")
            elif not message_text:
                self._error_label.setText("請輸入紀錄內容（必填）")
            else:
                self._error_label.setText("")
        if self._save_button is not None:
            self._save_button.setEnabled(valid)

    def _on_submit(self) -> None:
        action_text = self.action_combo.currentText().strip()
        message_text = self.message_input.toPlainText().strip()
        if not action_text or not message_text:
            self._update_validation()
            return
        try:
            audit_id = _anomaly_workbench_service.append_manual_audit(
                anomaly_id=self._anomaly_id,
                action=action_text,
                after_value=message_text,
                actor_name=self._actor_name,
            )
        except ValueError as exc:
            set_field_invalid(self.message_input, True)
            if self._error_label is not None:
                self._error_label.setText(localize_exception(exc))
            return
        except Exception as exc:
            set_field_invalid(self.message_input, True)
            if self._error_label is not None:
                self._error_label.setText(
                    localize_popup_message(
                        f"新增處理紀錄失敗：{localize_exception(exc)}"
                    )
                )
            return
        self._dirty = False
        self.audit_created.emit(audit_id)
        self.accept()
