"""Edit one canonical case Action from the anomaly workbench."""



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

    CASE_ACTION_TYPE_LABELS,

    CASE_ACTION_TYPE_NEXT_ACTION,

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





class EditAnomalyActionDialog(DirtyTrackingMixin, QDialog):

    """Edit an open Action's metadata through the workbench dialog."""



    action_updated = Signal(str)



    def __init__(self, action: dict, parent=None) -> None:

        super().__init__(parent)

        self._action = dict(action)

        self._action_id = str(self._action.get("id") or "").strip()

        if not self._action_id:

            raise ValueError("Action id is required")

        status = str(self._action.get("execution_status") or "")

        if status not in ("已規劃", "執行中"):

            raise ValueError("Only planned or in-progress Actions are editable")

        self.setWindowTitle("編輯 Action")

        self.setModal(True)

        self.setMinimumWidth(WORKBENCH_DIALOG_WIDE_MIN_WIDTH)

        self.setMaximumWidth(FORM_MAX_WIDTH)



        self.action_type_combo = QComboBox()

        action_type = str(self._action.get("action_type") or "")

        if action_type == CASE_ACTION_TYPE_NEXT_ACTION:

            self.action_type_combo.addItem(

                CASE_ACTION_TYPE_LABELS[CASE_ACTION_TYPE_NEXT_ACTION],

                CASE_ACTION_TYPE_NEXT_ACTION,

            )

            self.action_type_combo.setEnabled(False)

        else:

            for value, label in ordered_case_action_type_labels(for_ui=True):

                self.action_type_combo.addItem(label, value)

            index = self.action_type_combo.findData(action_type)

            if index >= 0:

                self.action_type_combo.setCurrentIndex(index)

        self.action_type_combo.setAccessibleName("Action 類型")



        self.action_items_input = ActionItemListWidget(

            placeholder="接下來要做什麼，例如向供應商要求 8D 報告"

        )

        self.action_items_input.set_from_legacy_description(

            str(self._action.get("description") or ""),

            default_owner=str(self._action.get("owner") or ""),

            default_due=str(self._action.get("due_date") or ""),

        )



        self.verify_check = QCheckBox("需要有效性驗證")

        self.verify_check.setAccessibleName("需要有效性驗證")

        self.verify_check.setChecked(bool(self._action.get("verification_required")))



        self._setup_ui()

        self._sync_verification_contract()

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

        form.addRow(QLabel("有效性驗證"), self.verify_check)

        lay.addLayout(form)

        buttons = QDialogButtonBox(

            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save

        )

        self._save_button = style_dialog_buttons(buttons)

        if self._save_button:

            self._save_button.setText("儲存 Action")

        buttons.accepted.connect(self._on_submit)

        buttons.rejected.connect(self.reject)

        apply_dialog_layout(self, content, buttons)



        self.action_items_input.valueChanged.connect(self._update_validation)

        self.action_type_combo.currentIndexChanged.connect(

            self._sync_verification_contract

        )



    def _connect_dirty_signals(self) -> None:

        self._init_dirty_tracking([

            self.action_items_input.valueChanged,

            self.action_type_combo.currentIndexChanged,

            self.verify_check.toggled,

        ])



    def _sync_verification_contract(self) -> None:

        action_type = str(self.action_type_combo.currentData() or "")

        eligible = action_type in CASE_ACTION_VERIFICATION_ELIGIBLE_TYPES

        self.verify_check.setEnabled(eligible)

        if not eligible:

            self.verify_check.setChecked(False)



    @property

    def _has_content(self) -> bool:

        return self.action_items_input.has_valid_content()



    def _update_validation(self) -> None:

        valid = self._has_content

        self.action_items_input.set_validation_invalid( not valid)

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

        action_type = str(self.action_type_combo.currentData() or "")

        verification_required = self.verify_check.isChecked()

        try:

            if len(items) == 1:

                item = items[0]

                _case_action_service.update_case_action(

                    self._action_id,

                    action_type=action_type,

                    description=item["description"],

                    owner=item["owner"],

                    due_date=item["due_date"],

                    verification_required=verification_required,

                )

                result_ids = [self._action_id]

            else:

                result_ids = _case_action_service.split_case_action(

                    self._action_id,

                    items,

                )

                if action_type != str(self._action.get("action_type") or ""):

                    for new_id in result_ids:

                        _case_action_service.update_case_action(

                            new_id,

                            action_type=action_type,

                            verification_required=verification_required,

                        )

                elif verification_required != bool(

                    self._action.get("verification_required")

                ):

                    for new_id in result_ids:

                        _case_action_service.update_case_action(

                            new_id,

                            verification_required=verification_required,

                        )

        except ValueError as exc:

            self.action_items_input.set_validation_invalid( True)

            if self._error_label is not None:

                self._error_label.setText(localize_exception(exc))

            return

        except Exception as exc:

            self.action_items_input.set_validation_invalid( True)

            if self._error_label is not None:

                self._error_label.setText(

                    localize_popup_message(

                        f"更新處置失敗：{localize_exception(exc)}"

                    )

                )

            return

        self._dirty = False

        self.action_updated.emit(result_ids[0])

        self.accept()

