from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from services import event_service
from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    FORM_HORIZONTAL_SPACING,
    FORM_VERTICAL_SPACING,
    FORM_MAX_WIDTH,
)
from ui.popup_i18n import localize_popup_message
from ui.window_sizing import fit_dialog_to_available_screen
from ui.widgets.common_widgets import (
    RequiredFieldLabel,
    apply_clickable_affordance,
    mark_button_variant,
    make_paired_form_row,
)
from ui.widgets.supplier_contact_manager_dialog import SupplierContactManagerDialog

logger = logging.getLogger(__name__)


class SupplierFormDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        initial_data: dict | None = None,
        is_edit: bool = False,
    ):
        super().__init__(parent)
        self._initial_data = initial_data or {}
        self._is_edit = is_edit
        self.setWindowTitle("編輯供應商" if self._is_edit else "新增供應商")
        self.setMinimumWidth(460)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        self._setup_ui()
        self._apply_initial_data()
        fit_dialog_to_available_screen(self, preferred_width=520)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        layout.setSpacing(FORM_VERTICAL_SPACING)

        form = QFormLayout()
        form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        form.setVerticalSpacing(FORM_VERTICAL_SPACING)

        self.supplier_name_input = QLineEdit()
        self.supplier_name_input.setPlaceholderText("輸入供應商名稱")
        self.contact_name_input = QLineEdit()
        self.contact_name_input.setPlaceholderText("主聯絡人姓名")
        self.department_input = QLineEdit()
        self.department_input.setPlaceholderText("部門")
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("電話/行動")
        self.contact_email_input = QLineEdit()
        self.contact_email_input.setPlaceholderText("電子郵件")

        form.addRow(RequiredFieldLabel("供應商名稱"), self.supplier_name_input)
        form.addRow(
            make_paired_form_row(
                "SupplierContactDeptRow",
                "主聯絡人",
                self.contact_name_input,
                "部門",
                self.department_input,
            )
        )
        form.addRow(
            make_paired_form_row(
                "SupplierPhoneEmailRow",
                "電話/行動",
                self.phone_input,
                "電子郵件",
                self.contact_email_input,
            )
        )

        if self._is_edit:
            self.btn_manage_contacts = QPushButton("管理多位聯絡人...")
            self.btn_manage_contacts.setProperty("variant", "secondary")
            apply_clickable_affordance(self.btn_manage_contacts)
            self.btn_manage_contacts.clicked.connect(self._manage_contacts)
            form.addRow("", self.btn_manage_contacts)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        mark_button_variant(save_button, "primary")
        mark_button_variant(cancel_button, "secondary")
        if save_button:
            save_button.setText("儲存")
        if cancel_button:
            cancel_button.setText("取消")
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_initial_data(self) -> None:
        self.supplier_name_input.setText(
            str(self._initial_data.get("supplier_name") or "")
        )
        self.contact_name_input.setText(str(self._initial_data.get("contact_name") or ""))
        self.department_input.setText(str(self._initial_data.get("department") or ""))
        self.phone_input.setText(str(self._initial_data.get("phone") or ""))
        self.contact_email_input.setText(str(self._initial_data.get("contact_email") or ""))

    def _manage_contacts(self) -> None:
        supplier_id = self._initial_data.get("id")
        if not supplier_id:
            return
        dialog = SupplierContactManagerDialog(
            supplier_id,
            supplier_name=self.supplier_name_input.text(),
            parent=self
        )
        dialog.exec()
        contacts = event_service.list_supplier_contacts(supplier_id)
        primary = next((c for c in contacts if c["is_primary"]), None)
        if primary:
            self.contact_name_input.setText(primary["contact_name"])
            self.department_input.setText(primary["department"])
            self.phone_input.setText(primary["phone"])
            self.contact_email_input.setText(primary["email"])

    def _on_submit(self) -> None:
        if not self.supplier_name_input.text().strip():
            QMessageBox.warning(
                self,
                "驗證失敗",
                localize_popup_message("供應商名稱為必填"),
            )
            return
        self.accept()

    def payload(self) -> dict:
        return {
            "supplier_name": self.supplier_name_input.text().strip(),
            "contact_name": self.contact_name_input.text().strip(),
            "department": self.department_input.text().strip(),
            "phone": self.phone_input.text().strip(),
            "contact_email": self.contact_email_input.text().strip(),
        }
