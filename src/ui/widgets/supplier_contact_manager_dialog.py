from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QFrame,
)

from services import event_service
from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    FORM_VERTICAL_SPACING,
)
from ui.widgets.common_widgets import (
    DirtyTrackingMixin,
    apply_clickable_affordance,
    make_inline_error_label,
    set_field_invalid,
    style_table,
)
from ui.window_sizing import fit_dialog_to_available_screen

logger = logging.getLogger(__name__)


class SupplierContactManagerDialog(DirtyTrackingMixin, QDialog):
    def __init__(self, supplier_id: str, supplier_name: str, parent=None):
        super().__init__(parent)
        self.supplier_id = supplier_id
        self.setWindowTitle(f"管理聯絡人 - {supplier_name}")
        self.setMinimumWidth(800)
        self._setup_ui()
        self._refresh_list()
        # Contacts persist per-action; the only unsaved state is a half-typed
        # new contact row, so dirty tracking watches just those add-row inputs.
        self._init_dirty_tracking([
            self.new_name.textChanged,
            self.new_dept.textChanged,
            self.new_phone.textChanged,
            self.new_email.textChanged,
        ])
        self.new_name.textChanged.connect(self._clear_validation)
        fit_dialog_to_available_screen(self, preferred_width=900, preferred_height=620)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        layout.setSpacing(FORM_VERTICAL_SPACING)

        # Top form for adding new contact
        add_group = QFrame()
        add_group.setProperty("role", "panel")
        add_layout = QVBoxLayout(add_group)

        add_title = QLabel("新增聯絡資料")
        add_title.setProperty("role", "sectionTitle")
        add_layout.addWidget(add_title)

        form = QHBoxLayout()
        form.setSpacing(8)

        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("姓名 *")
        self.new_dept = QLineEdit()
        self.new_dept.setPlaceholderText("部門")
        self.new_phone = QLineEdit()
        self.new_phone.setPlaceholderText("電話")
        self.new_email = QLineEdit()
        self.new_email.setPlaceholderText("Email")

        self.btn_add = QPushButton("新增")
        self.btn_add.setProperty("variant", "primary")
        apply_clickable_affordance(self.btn_add)
        self.btn_add.clicked.connect(self._on_add)

        form.addWidget(self.new_name)
        form.addWidget(self.new_dept)
        form.addWidget(self.new_phone)
        form.addWidget(self.new_email)
        form.addWidget(self.btn_add)
        add_layout.addLayout(form)
        self.inline_error = make_inline_error_label()
        add_layout.addWidget(self.inline_error)
        layout.addWidget(add_group)

        # List of contacts
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["姓名", "部門", "電話", "Email", "主聯絡人", "操作"])
        style_table(self.table)
        layout.addWidget(self.table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_list(self) -> None:
        contacts = event_service.list_supplier_contacts(self.supplier_id)
        self.table.setRowCount(len(contacts))
        for i, c in enumerate(contacts):
            self.table.setItem(i, 0, QTableWidgetItem(c["contact_name"]))
            self.table.setItem(i, 1, QTableWidgetItem(c["department"]))
            self.table.setItem(i, 2, QTableWidgetItem(c["phone"]))
            self.table.setItem(i, 3, QTableWidgetItem(c["email"]))

            is_p = c["is_primary"]
            p_text = "★ 是" if is_p else "否"
            self.table.setItem(i, 4, QTableWidgetItem(p_text))

            actions = QWidget()
            act_layout = QHBoxLayout(actions)
            act_layout.setContentsMargins(4, 2, 4, 2)
            act_layout.setSpacing(4)

            if not is_p:
                btn_p = QPushButton("設為主聯絡人")
                btn_p.setProperty("variant", "link")
                btn_p.clicked.connect(lambda _, cid=c["id"]: self._on_set_primary(cid))
                act_layout.addWidget(btn_p)

                btn_del = QPushButton("刪除")
                btn_del.setProperty("variant", "danger")
                btn_del.clicked.connect(lambda _, cid=c["id"]: self._on_delete(cid))
                act_layout.addWidget(btn_del)

            act_layout.addStretch()
            self.table.setCellWidget(i, 5, actions)
        self.table.resizeColumnsToContents()

    def _on_add(self) -> None:
        name = self.new_name.text().strip()
        if not name:
            set_field_invalid(self.new_name, True)
            self.inline_error.setText("姓名為必填，請輸入聯絡人姓名")
            self.inline_error.setVisible(True)
            self.new_name.setFocus()
            return

        event_service.add_supplier_contact(self.supplier_id, {
            "contact_name": name,
            "department": self.new_dept.text().strip(),
            "phone": self.new_phone.text().strip(),
            "email": self.new_email.text().strip(),
            "is_primary": False
        })
        self.new_name.clear()
        self.new_dept.clear()
        self.new_phone.clear()
        self.new_email.clear()
        self._clear_validation()
        self._refresh_list()
        self._dirty = False

    def _clear_validation(self, *args) -> None:
        set_field_invalid(self.new_name, False)
        self.inline_error.setVisible(False)

    def _on_set_primary(self, contact_id: str) -> None:
        event_service.set_primary_contact(self.supplier_id, contact_id)
        self._refresh_list()

    def _on_delete(self, contact_id: str) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("確認刪除")
        box.setText("確定要刪除此聯絡人嗎？")
        box.setIcon(QMessageBox.Icon.Warning)
        btn_yes = box.addButton("刪除", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(btn_yes)
        box.exec()
        if box.clickedButton() is not btn_yes:
            return
        event_service.delete_supplier_contact(contact_id)
        self._refresh_list()
