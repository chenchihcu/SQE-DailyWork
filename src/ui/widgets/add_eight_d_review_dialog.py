"""Append a Supplier 8D review entry from the anomaly workbench."""

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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from ui.layout_constants import WORKBENCH_DIALOG_WIDE_MIN_WIDTH

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


REVIEW_STATUS_OPTIONS = [
    ("接受", "接受"),
    ("退回修正", "退回修正"),
    ("需補充證據", "需補充證據"),
]


class AddEightDReviewDialog(DirtyTrackingMixin, QDialog):
    """Append a Supplier 8D review row with a matching audit entry."""

    review_created = Signal(str)

    def __init__(
        self,
        anomaly_id: str,
        next_revision_hint: str = "",
        parent=None,
        *,
        actor_name: str = "",
    ) -> None:
        super().__init__(parent)
        self._anomaly_id = (anomaly_id or "").strip()
        if not self._anomaly_id:
            raise ValueError("Anomaly id is required")
        self._actor_name = (actor_name or "").strip()
        self.setWindowTitle("追加 Supplier 8D 審查")
        self.setModal(True)
        self.setMinimumWidth(WORKBENCH_DIALOG_WIDE_MIN_WIDTH)
        self.setMaximumWidth(FORM_MAX_WIDTH)

        self.revision_input = QLineEdit()
        self.revision_input.setPlaceholderText("例如：Rev A、Rev B…")
        if next_revision_hint:
            self.revision_input.setText(next_revision_hint)

        self.status_combo = QComboBox()
        for value, label in REVIEW_STATUS_OPTIONS:
            self.status_combo.addItem(label, value)
        self.status_combo.setCurrentIndex(2)  # 需補充證據 is the safe default

        self.comment_input = QTextEdit()
        self.comment_input.setPlaceholderText("審查意見（選填）")
        self.comment_input.setAcceptRichText(False)

        self.review_date_edit = QDateEdit()
        self.review_date_edit.setCalendarPopup(True)
        self.review_date_edit.setDate(QDate.currentDate())
        self.review_date_edit.setDisplayFormat("yyyy-MM-dd")

        self._setup_ui()
        self._update_validation()
        self._connect_dirty_signals()

    def _setup_ui(self) -> None:
        content = QWidget()
        lay = QVBoxLayout(content)
        lay.setContentsMargins(*DIALOG_OUTER_MARGINS)
        lay.setSpacing(FORM_VERTICAL_SPACING)

        hint = QLabel("送出後將會以 append-only 形式寫入 Supplier 8D，並於處理歷程留下一筆審查紀錄。")
        hint.setProperty("role", "helperText")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        form = QFormLayout()
        form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        form.addRow(RequiredFieldLabel("版次"), self.revision_input)
        form.addRow("審查結果", self.status_combo)
        form.addRow("審查日期", self.review_date_edit)
        form.addRow("審查意見", self.comment_input)
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
            self._save_button.setText("追加審查")
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        apply_dialog_layout(self, scroll, buttons)

        self.revision_input.textChanged.connect(self._update_validation)

    def _connect_dirty_signals(self) -> None:
        self._init_dirty_tracking([
            self.revision_input.textChanged,
            self.status_combo.currentIndexChanged,
            self.review_date_edit.dateChanged,
            self.comment_input.textChanged,
        ])

    @property
    def _has_revision(self) -> bool:
        return bool(self.revision_input.text().strip())

    def _update_validation(self) -> None:
        valid = self._has_revision
        set_field_invalid(self.revision_input, not valid)
        if self._error_label is not None:
            self._error_label.setText(
                "" if valid else "請輸入版次（必填）"
            )
        if self._save_button is not None:
            self._save_button.setEnabled(valid)

    def _on_submit(self) -> None:
        revision = self.revision_input.text().strip()
        if not revision:
            self._update_validation()
            return
        try:
            review_id, _audit_id = _anomaly_workbench_service.create_eight_d_review_with_audit(
                anomaly_id=self._anomaly_id,
                revision=revision,
                review_status=str(self.status_combo.currentData() or "需補充證據"),
                review_comment=self.comment_input.toPlainText().strip(),
                review_date=self.review_date_edit.date().toString("yyyy-MM-dd"),
                actor_name=self._actor_name,
            )
        except ValueError as exc:
            set_field_invalid(self.revision_input, True)
            if self._error_label is not None:
                self._error_label.setText(localize_exception(exc))
            return
        except Exception as exc:
            set_field_invalid(self.revision_input, True)
            if self._error_label is not None:
                self._error_label.setText(
                    localize_popup_message(
                        f"追加 8D 審查失敗：{localize_exception(exc)}"
                    )
                )
            return
        self._dirty = False
        self.review_created.emit(review_id)
        self.accept()
