"""Root cause edit dialog for the anomaly case-workbench."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from ui.layout_constants import WORKBENCH_DIALOG_WIDE_MIN_WIDTH

from database.repo_helpers import (
    ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED,
    ANOMALY_ROOT_CAUSE_NOT_STARTED,
    ANOMALY_ROOT_CAUSE_PROPOSED,
    ANOMALY_ROOT_CAUSE_STATUSES,
    ANOMALY_ROOT_CAUSE_UNDER_INVESTIGATION,
    ANOMALY_ROOT_CAUSE_VERIFIED,
)
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

class AnomalyRootCauseDialog(DirtyTrackingMixin, QDialog):
    """Create or update the single root-cause record for an anomaly."""

    root_cause_saved = Signal(str)

    def __init__(
        self,
        anomaly_id: str,
        *,
        initial: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._anomaly_id = anomaly_id.strip()
        initial = initial or {}
        self.setWindowTitle("編輯根本原因")
        self.setModal(True)
        self.setMinimumWidth(WORKBENCH_DIALOG_WIDE_MIN_WIDTH)
        self.setMaximumWidth(FORM_MAX_WIDTH)

        self.statement_input = QTextEdit()
        self.statement_input.setPlaceholderText("根本原因是什麼？")
        self.statement_input.setAcceptRichText(False)
        self.statement_input.setPlainText(str(initial.get("statement") or ""))

        self.status_combo = QComboBox()
        for status in ANOMALY_ROOT_CAUSE_STATUSES:
            self.status_combo.addItem(status, status)
        current_status = str(initial.get("status") or ANOMALY_ROOT_CAUSE_NOT_STARTED)
        status_index = self.status_combo.findData(current_status)
        self.status_combo.setCurrentIndex(max(status_index, 0))

        self.validation_method_input = QTextEdit()
        self.validation_method_input.setPlaceholderText("如 5-Why、Fishbone、8D D4")
        self.validation_method_input.setAcceptRichText(False)
        self.validation_method_input.setFixedHeight(56)
        self.validation_method_input.setPlainText(str(initial.get("validation_method") or ""))

        self.validation_evidence_input = QTextEdit()
        self.validation_evidence_input.setPlaceholderText("支持 Root Cause 的證據")
        self.validation_evidence_input.setAcceptRichText(False)
        self.validation_evidence_input.setFixedHeight(56)
        self.validation_evidence_input.setPlainText(str(initial.get("validation_evidence") or ""))

        self.conclusion_input = QTextEdit()
        self.conclusion_input.setPlaceholderText("信心程度、待確認事項、建議後續驗證")
        self.conclusion_input.setAcceptRichText(False)
        self.conclusion_input.setFixedHeight(56)
        self.conclusion_input.setPlainText(str(initial.get("conclusion_note") or ""))

        self.not_established_input = QTextEdit()
        self.not_established_input.setPlaceholderText("Root Cause 狀態為「無法確認」時必填")
        self.not_established_input.setAcceptRichText(False)
        self.not_established_input.setFixedHeight(56)
        self.not_established_input.setPlainText(str(initial.get("not_established_reason") or ""))

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
        form.addRow(RequiredFieldLabel("Root Cause 說明"), self.statement_input)
        self._statement_error = make_inline_error_label()
        form.addRow("", self._statement_error)
        form.addRow(RequiredFieldLabel("狀態"), self.status_combo)
        form.addRow("驗證方式", self.validation_method_input)
        form.addRow("驗證證據", self.validation_evidence_input)
        form.addRow("結論說明", self.conclusion_input)
        form.addRow(RequiredFieldLabel("無法確認原因說明"), self.not_established_input)
        self._not_established_error = make_inline_error_label()
        form.addRow("", self._not_established_error)
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
            self._save_button.setText("儲存 Root Cause")
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        apply_dialog_layout(self, scroll, buttons)

        self.statement_input.textChanged.connect(self._update_validation)
        self.status_combo.currentIndexChanged.connect(self._update_validation)
        self.not_established_input.textChanged.connect(self._update_validation)

    def _connect_dirty_signals(self) -> None:
        self._init_dirty_tracking([
            self.statement_input.textChanged,
            self.status_combo.currentIndexChanged,
            self.validation_method_input.textChanged,
            self.validation_evidence_input.textChanged,
            self.conclusion_input.textChanged,
            self.not_established_input.textChanged,
        ])

    def _current_status(self) -> str:
        return str(self.status_combo.currentData() or ANOMALY_ROOT_CAUSE_NOT_STARTED)

    def _update_validation(self) -> None:
        status = self._current_status()
        statement = self.statement_input.toPlainText().strip()
        not_established = self.not_established_input.toPlainText().strip()
        statement_required = status in (
            ANOMALY_ROOT_CAUSE_VERIFIED,
            ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED,
        )
        statement_valid = (not statement_required) or bool(statement)
        not_established_required = status == ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED
        not_established_valid = (not not_established_required) or bool(not_established)
        valid = statement_valid and not_established_valid

        set_field_invalid(self.statement_input, not statement_valid)
        if self._statement_error is not None:
            self._statement_error.setText(
                ""
                if statement_valid
                else "此狀態需填寫 Root Cause 說明（必填）"
            )
        set_field_invalid(self.not_established_input, not not_established_valid)
        if self._not_established_error is not None:
            self._not_established_error.setText(
                ""
                if not_established_valid
                else "狀態為「無法確認」時需填寫原因說明（必填）"
            )
        if self._save_button is not None:
            self._save_button.setEnabled(valid)

    def _on_submit(self) -> None:
        self._update_validation()
        if self._save_button is not None and not self._save_button.isEnabled():
            return
        try:
            root_cause_id = _anomaly_workbench_service.save_root_cause(
                anomaly_id=self._anomaly_id,
                statement=self.statement_input.toPlainText().strip(),
                status=self._current_status(),
                validation_method=self.validation_method_input.toPlainText().strip(),
                validation_evidence=self.validation_evidence_input.toPlainText().strip(),
                conclusion_note=self.conclusion_input.toPlainText().strip(),
                not_established_reason=self.not_established_input.toPlainText().strip(),
            )
        except ValueError as exc:
            message = localize_exception(exc)
            if "statement" in str(exc).lower():
                set_field_invalid(self.statement_input, True)
                if self._statement_error is not None:
                    self._statement_error.setText(message)
            elif "not established" in str(exc).lower() or "無法確認" in message:
                set_field_invalid(self.not_established_input, True)
                if self._not_established_error is not None:
                    self._not_established_error.setText(message)
            return
        except Exception as exc:
            set_field_invalid(self.statement_input, True)
            if self._statement_error is not None:
                self._statement_error.setText(
                    localize_popup_message(f"儲存失敗：{localize_exception(exc)}")
                )
            return
        self._dirty = False
        self.root_cause_saved.emit(root_cause_id)
        self.accept()
