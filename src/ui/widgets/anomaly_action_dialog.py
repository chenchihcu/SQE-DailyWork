"""Create one canonical case Action from the anomaly workbench."""



from __future__ import annotations



from PySide6.QtCore import Signal

from PySide6.QtWidgets import (

    QCheckBox,

    QComboBox,

    QDialog,

    QDialogButtonBox,

    QFormLayout,

    QLabel,

    QVBoxLayout,

    QWidget,

)

from ui.layout_constants import WORKBENCH_DIALOG_WIDE_MIN_WIDTH



from database.repo_helpers import (

    CASE_ACTION_TYPE_CONTAINMENT,

    CASE_ACTION_VERIFICATION_ELIGIBLE_TYPES,

    ordered_case_action_type_labels,

)

from services.event import _case_action_service

from ui.layout_constants import (

    DIALOG_OUTER_MARGINS,

    FORM_HORIZONTAL_SPACING,

    FORM_MAX_WIDTH,

    FORM_VERTICAL_SPACING,

)

from ui.popup_i18n import localize_exception, localize_popup_message

from ui.widgets.action_item_list_widget import ActionItemListWidget

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

    """Create typed Actions with per-row owner and due date."""



    action_created = Signal(str)



    def __init__(self, anomaly_id: str, parent=None) -> None:

        super().__init__(parent)

        self._anomaly_id = anomaly_id.strip()

        self.setWindowTitle("新增 Action")

        self.setModal(True)

        self.setMinimumWidth(WORKBENCH_DIALOG_WIDE_MIN_WIDTH)

        self.setMaximumWidth(FORM_MAX_WIDTH)



        self.action_type_combo = QComboBox()

        for value, label in ordered_case_action_type_labels(for_ui=True):

            self.action_type_combo.addItem(label, value)

        containment_index = self.action_type_combo.findData(

            CASE_ACTION_TYPE_CONTAINMENT

        )

        if containment_index >= 0:

            self.action_type_combo.setCurrentIndex(containment_index)

        self.action_type_combo.setAccessibleName("Action 類型")



        self.action_items_input = ActionItemListWidget(

            placeholder="接下來要做什麼，例如向供應商要求 8D 報告"

        )



        self.execution_status_combo = QComboBox()

        self.execution_status_combo.addItem("已規劃", "已規劃")

        self.execution_status_combo.addItem("執行中", "執行中")

        self.execution_status_combo.setAccessibleName("執行狀態")



        self.verify_check = QCheckBox("需要有效性驗證")

        self.verify_check.setAccessibleName("需要有效性驗證")



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

        form.addRow(QLabel("Action 類型"), self.action_type_combo)

        form.addRow(RequiredFieldLabel("Action 內容"), self.action_items_input)

        self._error_label = make_inline_error_label()

        form.addRow("", self._error_label)

        form.addRow(QLabel("執行狀態"), self.execution_status_combo)

        form.addRow(QLabel("有效性驗證"), self.verify_check)

        lay.addLayout(form)

        buttons = QDialogButtonBox(

            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save

        )

        self._save_button = style_dialog_buttons(buttons)

        if self._save_button:

            self._save_button.setText("建立 Action")

        buttons.accepted.connect(self._on_submit)

        buttons.rejected.connect(self.reject)

        apply_dialog_layout(self, content, buttons)



        self.action_items_input.valueChanged.connect(self._update_validation)

        self.action_type_combo.currentIndexChanged.connect(

            self._sync_verification_contract

        )

        self._sync_verification_contract()



    def _connect_dirty_signals(self) -> None:

        self._init_dirty_tracking([

            self.action_items_input.valueChanged,

            self.action_type_combo.currentIndexChanged,

            self.execution_status_combo.currentIndexChanged,

            self.verify_check.toggled,

        ])



    def _sync_verification_contract(self) -> None:

        action_type = str(self.action_type_combo.currentData() or "")

        eligible = action_type in CASE_ACTION_VERIFICATION_ELIGIBLE_TYPES

        self.verify_check.setEnabled(eligible)

        self.verify_check.setChecked(eligible)



    @property

    def _has_content(self) -> bool:

        return self.action_items_input.has_valid_content()



    def _update_validation(self) -> None:

        valid = self._has_content

        self.action_items_input.set_validation_invalid(not valid)

        if self._error_label is not None:

            self._error_label.setText(

                "" if valid else "請輸入 Action 內容（必填）"

            )

        if self._save_button is not None:

            self._save_button.setEnabled(valid)



    def _on_submit(self) -> None:

        items = self.action_items_input.get_items()

        if not items:

            self._update_validation()

            return

        try:

            created_ids = _case_action_service.create_case_actions_batch(

                anomaly_id=self._anomaly_id,

                items=items,

                action_type=str(self.action_type_combo.currentData() or ""),

                execution_status=str(

                    self.execution_status_combo.currentData() or "已規劃"

                ),

                verification_required=self.verify_check.isChecked(),

            )

        except ValueError as exc:

            self.action_items_input.set_validation_invalid(True)

            if self._error_label is not None:

                self._error_label.setText(localize_exception(exc))

            return

        except Exception as exc:

            self.action_items_input.set_validation_invalid(True)

            if self._error_label is not None:

                self._error_label.setText(

                    localize_popup_message(

                        f"建立處置失敗：{localize_exception(exc)}"

                    )

                )

            return

        self._dirty = False

        self.action_created.emit(created_ids[0])

        self.accept()

