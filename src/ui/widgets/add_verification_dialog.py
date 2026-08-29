"""Add an effectiveness verification for a corrective action."""

from __future__ import annotations

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
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


RESULT_OPTIONS = [
    ("待驗證", "待驗證"),
    ("有效", "有效"),
    ("無效", "無效"),
    ("無法判定", "無法判定"),
]


class AddVerificationDialog(DirtyTrackingMixin, QDialog):
    """Append an effectiveness verification for a corrective action."""

    verification_created = Signal(str)

    def __init__(
        self,
        action_id: str,
        description: str = "",
        parent=None,
        *,
        actor_name: str = "",
    ) -> None:
        super().__init__(parent)
        self._action_id = (action_id or "").strip()
        if not self._action_id:
            raise ValueError("Action id is required")
        self._actor_name = (actor_name or "").strip()
        self.setWindowTitle("新增有效性驗證")
        self.setModal(True)
        self.setMinimumWidth(WORKBENCH_DIALOG_WIDE_MIN_WIDTH)
        self.setMaximumWidth(FORM_MAX_WIDTH)

        self.method_input = QLineEdit()
        self.method_input.setPlaceholderText("例如：30 天監控、抽樣檢驗…")

        self.criteria_input = QLineEdit()
        self.criteria_input.setPlaceholderText("例如：NG 率 < 0.5%")

        self.sample_input = QLineEdit()
        self.sample_input.setPlaceholderText("例如：3 批、200 pcs")

        self.result_combo = QComboBox()
        for value, label in RESULT_OPTIONS:
            self.result_combo.addItem(label, value)
        self.result_combo.setCurrentIndex(0)

        self.evidence_input = BulletListWidget(
            placeholder="驗證證據說明（照片、量測數據…）"
        )

        self.conclusion_input = BulletListWidget(placeholder="驗證結論（選填）")

        self.verified_by_input = QLineEdit()
        self.verified_by_input.setPlaceholderText("驗證人")

        self.verified_date_edit = QDateEdit()
        self.verified_date_edit.setCalendarPopup(True)
        self.verified_date_edit.setDate(QDate.currentDate())
        self.verified_date_edit.setDisplayFormat("yyyy-MM-dd")

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

        form = QFormLayout()
        form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        form.addRow(RequiredFieldLabel("驗證方法"), self.method_input)
        form.addRow("接受標準", self.criteria_input)
        form.addRow("期間 / 樣本", self.sample_input)
        form.addRow("驗證結果", self.result_combo)
        form.addRow("驗證證據", self.evidence_input)
        form.addRow("驗證結論", self.conclusion_input)
        form.addRow("驗證人", self.verified_by_input)
        form.addRow("驗證日期", self.verified_date_edit)
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
            self._save_button.setText("建立驗證")
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        apply_dialog_layout(self, scroll, buttons)

        self.method_input.textChanged.connect(self._update_validation)

    def _connect_dirty_signals(self) -> None:
        self._init_dirty_tracking([
            self.method_input.textChanged,
            self.criteria_input.textChanged,
            self.sample_input.textChanged,
            self.result_combo.currentIndexChanged,
            self.evidence_input.valueChanged,
            self.conclusion_input.valueChanged,
            self.verified_by_input.textChanged,
            self.verified_date_edit.dateChanged,
        ])

    @property
    def _has_method(self) -> bool:
        return bool(self.method_input.text().strip())

    def _update_validation(self) -> None:
        valid = self._has_method
        set_field_invalid(self.method_input, not valid)
        if self._error_label is not None:
            self._error_label.setText(
                "" if valid else "請輸入驗證方法（必填）"
            )
        if self._save_button is not None:
            self._save_button.setEnabled(valid)

    def _on_submit(self) -> None:
        method = self.method_input.text().strip()
        if not method:
            self._update_validation()
            return
        try:
            verification_id = _case_action_service.record_action_verification(
                action_id=self._action_id,
                method=method,
                acceptance_criteria=self.criteria_input.text().strip(),
                period_sample=self.sample_input.text().strip(),
                result=str(self.result_combo.currentData() or "待驗證"),
                evidence=self.evidence_input.get_formatted_text().strip(),
                conclusion=self.conclusion_input.get_formatted_text().strip(),
                verified_by=self.verified_by_input.text().strip(),
                verified_date=self.verified_date_edit.date().toString("yyyy-MM-dd"),
                actor_name=self._actor_name,
            )
        except ValueError as exc:
            set_field_invalid(self.method_input, True)
            if self._error_label is not None:
                self._error_label.setText(localize_exception(exc))
            return
        except Exception as exc:
            set_field_invalid(self.method_input, True)
            if self._error_label is not None:
                self._error_label.setText(
                    localize_popup_message(
                        f"建立驗證失敗：{localize_exception(exc)}"
                    )
                )
            return
        self._dirty = False
        self.verification_created.emit(verification_id)
        self.accept()
