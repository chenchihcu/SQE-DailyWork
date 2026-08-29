"""Focused canonical Action dialog for the 矯正措施 type."""

from __future__ import annotations

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from ui.layout_constants import WORKBENCH_DIALOG_WIDE_MIN_WIDTH

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
    RequiredFieldLabel,
    make_inline_error_label,
    set_field_invalid,
)
from ui.widgets.defect_form_widgets import (
    apply_dialog_layout,
    style_dialog_buttons,
)


class AddCorrectiveActionDialog(DirtyTrackingMixin, QDialog):
    """Create a new corrective action for an anomaly."""

    ca_created = Signal(str)

    def __init__(self, anomaly_id: str, parent=None) -> None:
        super().__init__(parent)
        self._anomaly_id = anomaly_id.strip()
        self.setWindowTitle("新增改善措施")
        self.setModal(True)
        self.setMinimumWidth(WORKBENCH_DIALOG_WIDE_MIN_WIDTH)
        self.setMaximumWidth(FORM_MAX_WIDTH)

        self.description_input = BulletListWidget(placeholder="將採取什麼矯正措施？")
        self.responsible_input = QLineEdit()
        self.responsible_input.setPlaceholderText("負責單位／人員（選填）")
        self.target_date_edit = QDateEdit()
        self.target_date_edit.setCalendarPopup(True)
        self.target_date_edit.setDate(QDate.currentDate().addDays(14))
        self.target_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.verify_check = QCheckBox("需進行有效性驗證")
        self.verify_check.setChecked(True)

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
        form.addRow(RequiredFieldLabel("措施內容"), self.description_input)
        self._error_label = make_inline_error_label()
        form.addRow("", self._error_label)
        form.addRow("負責單位／人員", self.responsible_input)
        form.addRow("預計完成日", self.target_date_edit)
        form.addRow("有效性驗證", self.verify_check)
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
            self._save_button.setText("建立改善措施")
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        apply_dialog_layout(self, scroll, buttons)
        self.description_input.valueChanged.connect(self._update_validation)

    def _connect_dirty_signals(self) -> None:
        self._init_dirty_tracking([
            self.description_input.valueChanged,
            self.responsible_input.textChanged,
            self.target_date_edit.dateChanged,
            self.verify_check.toggled,
        ])

    @property
    def _has_content(self) -> bool:
        return bool(self.description_input.get_formatted_text().strip())

    def _update_validation(self) -> None:
        valid = self._has_content
        set_field_invalid(self.description_input, not valid)
        if self._error_label is not None:
            self._error_label.setText("" if valid else "請輸入措施內容（必填）")
        if self._save_button is not None:
            self._save_button.setEnabled(valid)

    def _on_submit(self) -> None:
        description = self.description_input.get_formatted_text().strip()
        if not description:
            self._update_validation()
            return
        try:
            ca_id = _case_action_service.create_case_action(
                anomaly_id=self._anomaly_id,
                action_type="CORRECTIVE_ACTION",
                description=description,
                owner=self.responsible_input.text().strip(),
                due_date=self.target_date_edit.date().toString("yyyy-MM-dd"),
                execution_status="已規劃",
                verification_required=self.verify_check.isChecked(),
            )
        except ValueError as exc:
            set_field_invalid(self.description_input, True)
            if self._error_label is not None:
                self._error_label.setText(localize_exception(exc))
            return
        except Exception as exc:
            set_field_invalid(self.description_input, True)
            if self._error_label is not None:
                self._error_label.setText(
                    localize_popup_message(f"建立改善措施失敗：{localize_exception(exc)}")
                )
            return
        self._dirty = False
        self.ca_created.emit(ca_id)
        self.accept()
