"""Minimal next-action create dialog for the anomaly case-workbench.

Provides a small, well-scoped write entry point: create a next action
(description, owner, due date). Completing / cancelling an existing action is
left to the list view / future work; this dialog keeps the write path small and
consistent with the shared dialog-footer + required-field + dirty-guard
contracts.
"""

from __future__ import annotations

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from ui.layout_constants import WORKBENCH_DIALOG_WIDE_MIN_WIDTH

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
    RequiredFieldLabel,
    make_inline_error_label,
    set_field_invalid,
)
from ui.widgets.defect_form_widgets import (
    apply_dialog_layout,
    style_dialog_buttons,
)


class AddAnomalyActionDialog(DirtyTrackingMixin, QDialog):
    """Create a new next-action row for an existing anomaly."""

    action_created = Signal(str)

    def __init__(self, anomaly_id: str, parent=None) -> None:
        super().__init__(parent)
        self._anomaly_id = anomaly_id.strip()
        self.setWindowTitle("新增處置")
        self.setModal(True)
        self.setMinimumWidth(WORKBENCH_DIALOG_WIDE_MIN_WIDTH)
        self.setMaximumWidth(FORM_MAX_WIDTH)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("接下來要做什麼，例如向供應商要求 8D 報告")
        self.description_input.setAcceptRichText(False)

        self.owner_input = QLineEdit()
        self.owner_input.setPlaceholderText("負責人（選填）")

        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDate(QDate.currentDate().addDays(7))
        self.due_date_edit.setDisplayFormat("yyyy-MM-dd")

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
        form.addRow(RequiredFieldLabel("處置內容"), self.description_input)
        self._error_label = make_inline_error_label()
        form.addRow("", self._error_label)
        form.addRow(QLabel("負責人"), self.owner_input)
        form.addRow(QLabel("到期日"), self.due_date_edit)
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
            self._save_button.setText("建立處置")
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        apply_dialog_layout(self, scroll, buttons)

        self.description_input.textChanged.connect(self._update_validation)

    def _connect_dirty_signals(self) -> None:
        self._init_dirty_tracking([
            self.description_input.textChanged,
            self.owner_input.textChanged,
            self.due_date_edit.dateChanged,
        ])

    @property
    def _has_content(self) -> bool:
        return bool(self.description_input.toPlainText().strip())

    def _update_validation(self) -> None:
        valid = self._has_content
        set_field_invalid(self.description_input, not valid)
        if self._error_label is not None:
            self._error_label.setText(
                "" if valid else "請輸入處置內容（必填）"
            )
        if self._save_button is not None:
            self._save_button.setEnabled(valid)

    def _on_submit(self) -> None:
        description = self.description_input.toPlainText().strip()
        if not description:
            self._update_validation()
            return
        owner = self.owner_input.text().strip()
        due = self.due_date_edit.date().toString("yyyy-MM-dd")
        try:
            action_id = _anomaly_action_service.create_action(
                anomaly_id=self._anomaly_id,
                description=description,
                owner=owner,
                due_date=due,
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
                    localize_popup_message(
                        f"建立處置失敗：{localize_exception(exc)}"
                    )
                )
            return
        self._dirty = False
        self.action_created.emit(action_id)
        self.accept()
