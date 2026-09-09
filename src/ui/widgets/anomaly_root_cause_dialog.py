"""Root cause edit dialog for the anomaly case-workbench."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from ui.layout_constants import WORKBENCH_DIALOG_WIDE_MIN_WIDTH
from ui.window_sizing import _available_geometry, _usable_extent, fit_dialog_to_available_screen

from database.repo_helpers import (
    ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED,
    ANOMALY_ROOT_CAUSE_NOT_STARTED,
    ANOMALY_ROOT_CAUSE_STATUSES,
    ANOMALY_ROOT_CAUSE_VERIFIED,
)
from services.event import _anomaly_workbench_service
from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    DIALOG_SCREEN_FRACTION,
    DIALOG_SCREEN_MARGIN_Y,
    FORM_HORIZONTAL_SPACING,
    FORM_MAX_WIDTH,
    FORM_VERTICAL_SPACING,
    GRID_GUTTER,
    ROW_GAP,
    WORKBENCH_ROOT_CAUSE_DIALOG_PREFERRED_HEIGHT,
    WORKBENCH_ROOT_CAUSE_DIALOG_PREFERRED_WIDTH,
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


class AnomalyRootCauseDialog(DirtyTrackingMixin, QDialog):
    """Create or update the single root-cause record for an anomaly."""

    root_cause_saved = Signal(str)

    _BODY_FOOTER_ESTIMATE = 72

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
        self._scroll: QScrollArea | None = None
        self.setWindowTitle("編輯根本原因")
        self.setModal(True)
        self.setMinimumWidth(WORKBENCH_DIALOG_WIDE_MIN_WIDTH)
        self.setMaximumWidth(FORM_MAX_WIDTH)

        bullet_kwargs = {"compact_add_button": True}

        self.statement_input = BulletListWidget(
            placeholder="根本原因是什麼？",
            **bullet_kwargs,
        )
        self.statement_input.set_formatted_text(str(initial.get("statement") or ""))

        self.status_combo = QComboBox()
        for status in ANOMALY_ROOT_CAUSE_STATUSES:
            self.status_combo.addItem(status, status)
        current_status = str(initial.get("status") or ANOMALY_ROOT_CAUSE_NOT_STARTED)
        status_index = self.status_combo.findData(current_status)
        self.status_combo.setCurrentIndex(max(status_index, 0))

        self.validation_method_input = BulletListWidget(
            placeholder="如 5-Why、Fishbone、8D D4",
            **bullet_kwargs,
        )
        self.validation_method_input.set_formatted_text(
            str(initial.get("validation_method") or "")
        )

        self.validation_evidence_input = BulletListWidget(
            placeholder="支持根本原因的證據",
            **bullet_kwargs,
        )
        self.validation_evidence_input.set_formatted_text(
            str(initial.get("validation_evidence") or "")
        )

        self.conclusion_input = BulletListWidget(
            placeholder="信心程度、待確認事項、建議後續驗證",
            **bullet_kwargs,
        )
        self.conclusion_input.set_formatted_text(
            str(initial.get("conclusion_note") or "")
        )

        self.not_established_input = BulletListWidget(
            placeholder="狀態為「無法確認」時必填",
            **bullet_kwargs,
        )
        self.not_established_input.set_formatted_text(
            str(initial.get("not_established_reason") or "")
        )

        self._setup_ui()
        self._sync_not_established_visibility()
        self._update_validation()
        self._connect_dirty_signals()
        self._refit_dialog_geometry()

    def _setup_ui(self) -> None:
        self._content = QWidget()
        lay = QVBoxLayout(self._content)
        lay.setContentsMargins(*DIALOG_OUTER_MARGINS)
        lay.setSpacing(FORM_VERTICAL_SPACING)

        lay.addWidget(self._group_title("核心"))

        core_form = QFormLayout()
        core_form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        core_form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        core_form.addRow(RequiredFieldLabel("根本原因說明"), self.statement_input)
        self._statement_error = make_inline_error_label()
        core_form.addRow("", self._statement_error)
        core_form.addRow(RequiredFieldLabel("狀態"), self.status_combo)
        lay.addLayout(core_form)

        lay.addWidget(self._group_title("驗證"))

        verify_grid = QGridLayout()
        verify_grid.setHorizontalSpacing(GRID_GUTTER)
        verify_grid.setVerticalSpacing(ROW_GAP)
        verify_grid.setColumnStretch(1, 1)
        verify_grid.setColumnStretch(3, 1)
        verify_grid.addWidget(QLabel("驗證方式"), 0, 0)
        verify_grid.addWidget(self.validation_method_input, 0, 1)
        verify_grid.addWidget(QLabel("驗證證據"), 0, 2)
        verify_grid.addWidget(self.validation_evidence_input, 0, 3)
        lay.addLayout(verify_grid)

        lay.addWidget(self._group_title("結論"))

        conclusion_form = QFormLayout()
        conclusion_form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        conclusion_form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        conclusion_form.addRow(QLabel("結論說明"), self.conclusion_input)
        lay.addLayout(conclusion_form)

        self._not_established_section = QWidget()
        not_established_layout = QVBoxLayout(self._not_established_section)
        not_established_layout.setContentsMargins(0, 0, 0, 0)
        not_established_layout.setSpacing(FORM_VERTICAL_SPACING)
        not_established_layout.addWidget(self._group_title("條件"))
        conditional_form = QFormLayout()
        conditional_form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        conditional_form.setVerticalSpacing(FORM_VERTICAL_SPACING)
        conditional_form.addRow(
            RequiredFieldLabel("無法確認原因"),
            self.not_established_input,
        )
        self._not_established_error = make_inline_error_label()
        conditional_form.addRow("", self._not_established_error)
        not_established_layout.addLayout(conditional_form)
        lay.addWidget(self._not_established_section)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self._save_button = style_dialog_buttons(buttons)
        if self._save_button:
            self._save_button.setText("儲存根本原因")
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        apply_dialog_layout(self, self._content, buttons)

        fit_dialog_to_available_screen(
            self,
            preferred_width=WORKBENCH_ROOT_CAUSE_DIALOG_PREFERRED_WIDTH,
            preferred_height=WORKBENCH_ROOT_CAUSE_DIALOG_PREFERRED_HEIGHT,
            maximum_width=FORM_MAX_WIDTH,
        )

        self.statement_input.valueChanged.connect(self._on_content_geometry_changed)
        self.status_combo.currentIndexChanged.connect(self._on_status_changed)
        self.not_established_input.valueChanged.connect(self._on_content_geometry_changed)
        for widget in (
            self.validation_method_input,
            self.validation_evidence_input,
            self.conclusion_input,
        ):
            widget.valueChanged.connect(self._on_content_geometry_changed)

    @staticmethod
    def _group_title(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "sectionTitle")
        return label

    def _connect_dirty_signals(self) -> None:
        self._init_dirty_tracking([
            self.statement_input.valueChanged,
            self.status_combo.currentIndexChanged,
            self.validation_method_input.valueChanged,
            self.validation_evidence_input.valueChanged,
            self.conclusion_input.valueChanged,
            self.not_established_input.valueChanged,
        ])

    def _on_status_changed(self) -> None:
        self._sync_not_established_visibility()
        self._update_validation()
        self._refit_dialog_geometry()

    def _on_content_geometry_changed(self) -> None:
        self._update_validation()
        self._refit_dialog_geometry()

    def _sync_not_established_visibility(self) -> None:
        visible = self._current_status() == ANOMALY_ROOT_CAUSE_NOT_ESTABLISHED
        self._not_established_section.setVisible(visible)

    def _usable_dialog_height(self) -> int:
        geometry = _available_geometry(self)
        if geometry is None:
            return WORKBENCH_ROOT_CAUSE_DIALOG_PREFERRED_HEIGHT
        return _usable_extent(
            geometry.height(),
            margin=DIALOG_SCREEN_MARGIN_Y,
            fraction=DIALOG_SCREEN_FRACTION,
            maximum=None,
        )

    def _natural_content_height(self) -> int:
        self._content.updateGeometry()
        return self._content.sizeHint().height() + self._BODY_FOOTER_ESTIMATE

    def _set_body_widget(self, body: QWidget) -> None:
        outer = self.layout()
        if outer is None or outer.count() == 0:
            return
        existing = outer.itemAt(0).widget()
        if existing is body:
            return
        outer.removeWidget(existing)
        existing.setParent(None)
        outer.insertWidget(0, body, 1)

    def _refit_dialog_geometry(self) -> None:
        natural_height = self._natural_content_height()
        usable_height = self._usable_dialog_height()
        needs_scroll = natural_height > usable_height

        if needs_scroll:
            if self._scroll is None:
                self._scroll = QScrollArea()
                self._scroll.setWidgetResizable(True)
                self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
                self._scroll.setHorizontalScrollBarPolicy(
                    Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                )
            self._scroll.setWidget(self._content)
            self._set_body_widget(self._scroll)
            preferred_height = usable_height
        else:
            if self._scroll is not None:
                self._scroll.setWidget(None)
            self._set_body_widget(self._content)
            preferred_height = max(
                WORKBENCH_ROOT_CAUSE_DIALOG_PREFERRED_HEIGHT,
                natural_height,
            )

        fit_dialog_to_available_screen(
            self,
            preferred_width=WORKBENCH_ROOT_CAUSE_DIALOG_PREFERRED_WIDTH,
            preferred_height=preferred_height,
            maximum_width=FORM_MAX_WIDTH,
        )

    def _current_status(self) -> str:
        return str(self.status_combo.currentData() or ANOMALY_ROOT_CAUSE_NOT_STARTED)

    def _update_validation(self) -> None:
        status = self._current_status()
        statement = self.statement_input.get_formatted_text().strip()
        not_established = self.not_established_input.get_formatted_text().strip()
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
                else "此狀態需填寫根本原因說明（必填）"
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
                statement=self.statement_input.get_formatted_text().strip(),
                status=self._current_status(),
                validation_method=self.validation_method_input.get_formatted_text().strip(),
                validation_evidence=self.validation_evidence_input.get_formatted_text().strip(),
                conclusion_note=self.conclusion_input.get_formatted_text().strip(),
                not_established_reason=self.not_established_input.get_formatted_text().strip(),
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
