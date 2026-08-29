"""Hypothesis create/edit dialog for the anomaly case-workbench."""

from __future__ import annotations

from PySide6.QtCore import Signal
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

from database.repo_helpers import (
    ANOMALY_EVIDENCE_LABELS,
    ANOMALY_EVIDENCE_TYPES,
    ANOMALY_EVIDENCE_UNKNOWN,
    ANOMALY_HYPOTHESIS_PROPOSED,
    ANOMALY_HYPOTHESIS_STATUSES,
)
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

class AnomalyHypothesisDialog(DirtyTrackingMixin, QDialog):
    """Create or update one multi-layer hypothesis node."""

    hypothesis_saved = Signal(str)

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
        self._hypothesis_id = str(initial.get("id") or "").strip()
        self.setWindowTitle("編輯假設" if self._hypothesis_id else "新增假設")
        self.setModal(True)
        self.setMinimumWidth(WORKBENCH_DIALOG_WIDE_MIN_WIDTH)
        self.setMaximumWidth(FORM_MAX_WIDTH)

        self.statement_input = BulletListWidget(placeholder="描述此層原因假設")
        self.statement_input.set_formatted_text(str(initial.get("statement") or ""))

        self.status_combo = QComboBox()
        for status in ANOMALY_HYPOTHESIS_STATUSES:
            self.status_combo.addItem(status, status)
        current_status = str(initial.get("status") or ANOMALY_HYPOTHESIS_PROPOSED)
        status_index = self.status_combo.findData(current_status)
        self.status_combo.setCurrentIndex(max(status_index, 0))

        self.evidence_combo = QComboBox()
        for value in ANOMALY_EVIDENCE_TYPES:
            label = ANOMALY_EVIDENCE_LABELS[value]
            self.evidence_combo.addItem(f"{label}（{value}）", value)
        evidence_index = self.evidence_combo.findData(
            str(initial.get("evidence_type") or ANOMALY_EVIDENCE_UNKNOWN)
        )
        self.evidence_combo.setCurrentIndex(max(evidence_index, 0))

        self.parent_combo = QComboBox()
        self.parent_combo.addItem("（第一層，無上層）", "")
        try:
            parent_rows = _anomaly_workbench_service.list_hypotheses(self._anomaly_id)
        except RuntimeError:
            parent_rows = []
        for hypothesis in parent_rows:
            hypothesis_id = str(hypothesis.get("id") or "")
            if hypothesis_id == self._hypothesis_id:
                continue
            level = int(hypothesis.get("level") or 1)
            indent = "　" * max(level - 1, 0)
            preview = str(hypothesis.get("statement") or "").replace("\n", " ").strip()
            self.parent_combo.addItem(
                f"{indent}L{level} {preview[:36]}",
                hypothesis_id,
            )
        parent_index = self.parent_combo.findData(
            str(initial.get("parent_hypothesis_id") or "")
        )
        self.parent_combo.setCurrentIndex(max(parent_index, 0))

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
        form.addRow(RequiredFieldLabel("假設說明"), self.statement_input)
        self._error_label = make_inline_error_label()
        form.addRow("", self._error_label)
        form.addRow("狀態", self.status_combo)
        form.addRow("證據分類", self.evidence_combo)
        form.addRow("上層假設", self.parent_combo)
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
            self._save_button.setText("儲存假設")
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        apply_dialog_layout(self, scroll, buttons)
        self.statement_input.valueChanged.connect(self._update_validation)

    def _connect_dirty_signals(self) -> None:
        self._init_dirty_tracking([
            self.statement_input.valueChanged,
            self.status_combo.currentIndexChanged,
            self.evidence_combo.currentIndexChanged,
            self.parent_combo.currentIndexChanged,
        ])

    def _update_validation(self) -> None:
        valid = bool(self.statement_input.get_formatted_text().strip())
        set_field_invalid(self.statement_input, not valid)
        if self._error_label is not None:
            self._error_label.setText("" if valid else "請輸入假設說明（必填）")
        if self._save_button is not None:
            self._save_button.setEnabled(valid)

    def _on_submit(self) -> None:
        statement = self.statement_input.get_formatted_text().strip()
        if not statement:
            self._update_validation()
            return
        status = str(self.status_combo.currentData() or ANOMALY_HYPOTHESIS_PROPOSED)
        evidence = str(self.evidence_combo.currentData() or ANOMALY_EVIDENCE_UNKNOWN)
        parent_id = str(self.parent_combo.currentData() or "") or None
        try:
            if self._hypothesis_id:
                _anomaly_workbench_service.update_hypothesis(
                    anomaly_id=self._anomaly_id,
                    hypothesis_id=self._hypothesis_id,
                    statement=statement,
                    status=status,
                    evidence_type=evidence,
                    parent_hypothesis_id=parent_id,
                )
                hypothesis_id = self._hypothesis_id
            else:
                hypothesis_id = _anomaly_workbench_service.create_hypothesis(
                    anomaly_id=self._anomaly_id,
                    statement=statement,
                    status=status,
                    evidence_type=evidence,
                    parent_hypothesis_id=parent_id,
                )
        except ValueError as exc:
            set_field_invalid(self.statement_input, True)
            if self._error_label is not None:
                self._error_label.setText(localize_exception(exc))
            return
        except Exception as exc:
            set_field_invalid(self.statement_input, True)
            if self._error_label is not None:
                self._error_label.setText(
                    localize_popup_message(f"儲存假設失敗：{localize_exception(exc)}")
                )
            return
        self._dirty = False
        self.hypothesis_saved.emit(hypothesis_id)
        self.accept()
