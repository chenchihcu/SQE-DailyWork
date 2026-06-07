from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from database.connection import get_connection
from database.product_stage import (
    PRODUCT_STAGE_MASS_PRODUCTION,
    PRODUCT_STAGE_OPTIONS,
    PRODUCT_STAGE_TRIAL_PRODUCTION,
    normalize_product_stage_ui,
)
from services import event_service, master_import_service
from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    FORM_HORIZONTAL_SPACING,
    FORM_VERTICAL_SPACING,
    FORM_MAX_WIDTH,
    PANEL_MARGINS,
    ROOT_SECTION_SPACING,
    TAB_CONTENT_TOP_MARGIN,
    TOOLBAR_CONTROL_MIN_HEIGHT,
    TOOLBAR_ITEM_SPACING,
)
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.window_sizing import fit_dialog_to_available_screen
from ui.widgets.common_widgets import (
    RequiredFieldLabel,
    apply_clickable_affordance,
    apply_table_action_affordance,
    create_status_item,
    style_table,
)
from ui.widgets.pagination_bar import PaginationBar


def _set_combo_current_data(combo: QComboBox, value: str) -> bool:
    idx = combo.findData(value)
    if idx < 0:
        return False
    combo.setCurrentIndex(idx)
    return True


def _mark_button_variant(button: QPushButton | None, variant: str) -> None:
    if button is None:
        return
    button.setProperty("variant", variant)
    apply_clickable_affordance(button)
    style = button.style()
    style.unpolish(button)
    style.polish(button)


def _paired_label(label: str | QWidget) -> QWidget:
    if isinstance(label, QWidget):
        return label
    return QLabel(label)


def _make_paired_form_row(
    object_name: str,
    left_label: str | QWidget,
    left_field: QWidget,
    right_label: str | QWidget,
    right_field: QWidget,
) -> QWidget:
    row = QWidget()
    row.setObjectName(object_name)
    grid = QGridLayout(row)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
    grid.setVerticalSpacing(0)
    grid.addWidget(_paired_label(left_label), 0, 0)
    grid.addWidget(left_field, 0, 1)
    grid.addWidget(_paired_label(right_label), 0, 2)
    grid.addWidget(right_field, 0, 3)
    grid.setColumnStretch(1, 1)
    grid.setColumnStretch(3, 1)
    return row


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
            _make_paired_form_row(
                "SupplierContactDeptRow",
                "主聯絡人",
                self.contact_name_input,
                "部門",
                self.department_input,
            )
        )
        form.addRow(
            _make_paired_form_row(
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
        _mark_button_variant(save_button, "primary")
        _mark_button_variant(cancel_button, "secondary")
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
        # After managing, we might want to refresh the main dialog if the primary contact changed
        # For simplicity, we just let the user know they might need to re-open if they want to see the new primary here
        # Or we could fetch the latest primary contact and update the fields.
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


class SupplierContactManagerDialog(QDialog):
    def __init__(self, supplier_id: str, supplier_name: str, parent=None):
        super().__init__(parent)
        self.supplier_id = supplier_id
        self.setWindowTitle(f"管理聯絡人 - {supplier_name}")
        self.setMinimumWidth(800)
        self._setup_ui()
        self._refresh_list()
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
        self.new_name.setPlaceholderText("姓名*")
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
                btn_del.setProperty("variant", "danger") # Or link
                btn_del.clicked.connect(lambda _, cid=c["id"]: self._on_delete(cid))
                act_layout.addWidget(btn_del)
            
            act_layout.addStretch()
            self.table.setCellWidget(i, 5, actions)
        self.table.resizeColumnsToContents()

    def _on_add(self) -> None:
        name = self.new_name.text().strip()
        if not name:
            QMessageBox.warning(self, "驗證失敗", "姓名為必填")
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
        self._refresh_list()

    def _on_set_primary(self, contact_id: str) -> None:
        event_service.set_primary_contact(self.supplier_id, contact_id)
        self._refresh_list()

    def _on_delete(self, contact_id: str) -> None:
        confirm = QMessageBox.question(self, "確認刪除", "確定要刪除此聯絡人嗎？")
        if confirm == QMessageBox.StandardButton.Yes:
            event_service.delete_supplier_contact(contact_id)
            self._refresh_list()


class ProductFormDialog(QDialog):
    def __init__(
        self,
        suppliers: list[dict],
        parent=None,
        *,
        initial_data: dict | None = None,
        is_edit: bool = False,
    ):
        super().__init__(parent)
        self._suppliers = suppliers
        self._initial_data = initial_data or {}
        self._is_edit = is_edit
        self._stage_change_reason = ""
        self.setWindowTitle("編輯產品" if self._is_edit else "新增產品")
        self.setMinimumWidth(560)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        self._setup_ui()
        self._apply_initial_data()
        fit_dialog_to_available_screen(self, preferred_width=640)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        layout.setSpacing(FORM_VERTICAL_SPACING)

        form = QFormLayout()
        form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        form.setVerticalSpacing(FORM_VERTICAL_SPACING)

        self.product_code_input = QLineEdit()
        self.product_code_input.setPlaceholderText("輸入料號")
        self.product_name_input = QLineEdit()
        self.product_name_input.setPlaceholderText("輸入品名")

        self.product_stage_combo = QComboBox()
        self.product_stage_combo.addItems(list(PRODUCT_STAGE_OPTIONS))
        self.product_stage_combo.setCurrentText(PRODUCT_STAGE_MASS_PRODUCTION)

        self.primary_supplier_combo = QComboBox()
        self.secondary_supplier_combo = QComboBox()
        self._load_supplier_options()

        form.addRow(
            _make_paired_form_row(
                "ProductCodeStageRow",
                RequiredFieldLabel("料號"),
                self.product_code_input,
                "階段",
                self.product_stage_combo,
            )
        )
        form.addRow(RequiredFieldLabel("品名"), self.product_name_input)
        form.addRow(RequiredFieldLabel("主供應商"), self.primary_supplier_combo)
        form.addRow("次要供應商 (2nd source)", self.secondary_supplier_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        _mark_button_variant(save_button, "primary")
        _mark_button_variant(cancel_button, "secondary")
        if save_button:
            save_button.setText("儲存")
        if cancel_button:
            cancel_button.setText("取消")
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_supplier_options(self) -> None:
        self.primary_supplier_combo.clear()
        self.primary_supplier_combo.addItem("請選擇主供應商 *", "")

        self.secondary_supplier_combo.clear()
        self.secondary_supplier_combo.addItem("（未指定）", "")

        for supplier in self._suppliers:
            supplier_id = str(supplier.get("id") or "").strip()
            if not supplier_id:
                continue
            name = str(supplier.get("supplier_name") or supplier_id)
            if not bool(supplier.get("is_active", True)):
                name = f"{name}（停用）"
            self.primary_supplier_combo.addItem(name, supplier_id)
            self.secondary_supplier_combo.addItem(name, supplier_id)

    def _apply_initial_data(self) -> None:
        self.product_code_input.setText(str(self._initial_data.get("product_code") or ""))
        self.product_name_input.setText(str(self._initial_data.get("product_name") or ""))
        self.product_stage_combo.setCurrentText(
            normalize_product_stage_ui(self._initial_data.get("product_stage"))
        )

        supplier_id = str(self._initial_data.get("supplier_id") or "").strip()
        if supplier_id and not _set_combo_current_data(self.primary_supplier_combo, supplier_id):
            self.primary_supplier_combo.addItem(f"{supplier_id}（目前值）", supplier_id)
            _set_combo_current_data(self.primary_supplier_combo, supplier_id)

        secondary_supplier_id = str(
            self._initial_data.get("secondary_supplier_id") or ""
        ).strip()
        if secondary_supplier_id and not _set_combo_current_data(
            self.secondary_supplier_combo, secondary_supplier_id
        ):
            self.secondary_supplier_combo.addItem(
                f"{secondary_supplier_id}（目前值）", secondary_supplier_id
            )
            _set_combo_current_data(self.secondary_supplier_combo, secondary_supplier_id)

    def _on_submit(self) -> None:
        product_code = self.product_code_input.text().strip()
        product_name = self.product_name_input.text().strip()
        supplier_id = str(self.primary_supplier_combo.currentData() or "").strip()
        secondary_supplier_id = str(
            self.secondary_supplier_combo.currentData() or ""
        ).strip()

        if not product_code:
            QMessageBox.warning(self, "驗證失敗", localize_popup_message("料號為必填"))
            return
        if not product_name:
            QMessageBox.warning(self, "驗證失敗", localize_popup_message("產品名稱為必填"))
            return
        if not supplier_id:
            QMessageBox.warning(self, "驗證失敗", localize_popup_message("供應商為必填"))
            return
        if secondary_supplier_id and secondary_supplier_id == supplier_id:
            QMessageBox.warning(
                self,
                "驗證失敗",
                localize_popup_message("2nd source 不可與主供應商相同"),
            )
            return
        previous_stage = normalize_product_stage_ui(self._initial_data.get("product_stage"))
        selected_stage = normalize_product_stage_ui(self.product_stage_combo.currentText())
        self._stage_change_reason = ""
        if (
            self._is_edit
            and previous_stage == PRODUCT_STAGE_MASS_PRODUCTION
            and selected_stage == PRODUCT_STAGE_TRIAL_PRODUCTION
        ):
            confirm = QMessageBox.question(
                self,
                "確認回退",
                localize_popup_message(
                    "即將將產品由量產改為試產，系統會同步更新歷史事件資料。是否繼續？"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            reason, ok = QInputDialog.getMultiLineText(
                self,
                "回退原因",
                "請輸入量產改回試產的原因（必填）：",
            )
            if not ok:
                return
            self._stage_change_reason = reason.strip()
            if not self._stage_change_reason:
                QMessageBox.warning(
                    self,
                    "驗證失敗",
                    localize_popup_message("量產改回試產時需填寫原因"),
                )
                return

        self.accept()

    def payload(self) -> dict:
        return {
            "product_code": self.product_code_input.text().strip(),
            "product_name": self.product_name_input.text().strip(),
            "product_stage": normalize_product_stage_ui(
                self.product_stage_combo.currentText()
            ),
            "supplier_id": str(self.primary_supplier_combo.currentData() or "").strip(),
            "secondary_supplier_id": str(
                self.secondary_supplier_combo.currentData() or ""
            ).strip(),
            "stage_change_reason": self._stage_change_reason,
        }


class ProductStageLogDialog(QDialog):
    def __init__(self, product_label: str, logs: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("產品階段異動紀錄")
        self.setMinimumWidth(920)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        layout.setSpacing(FORM_VERTICAL_SPACING)
        header = QLabel(f"產品：{product_label}")
        header.setProperty("role", "helperText")
        layout.addWidget(header)
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(
            [
                "異動時間",
                "原階段",
                "新階段",
                "原因",
                "同步範圍",
                "異常更新筆數",
                "訪廠更新筆數",
                "操作者",
            ]
        )
        style_table(table)
        table.setRowCount(len(logs))
        for row_idx, row in enumerate(logs):
            table.setItem(row_idx, 0, QTableWidgetItem(str(row.get("changed_at") or "")))
            table.setItem(row_idx, 1, QTableWidgetItem(str(row.get("from_stage") or "")))
            table.setItem(row_idx, 2, QTableWidgetItem(str(row.get("to_stage") or "")))
            table.setItem(row_idx, 3, QTableWidgetItem(str(row.get("reason") or "")))
            table.setItem(row_idx, 4, QTableWidgetItem(str(row.get("sync_scope") or "")))
            table.setItem(
                row_idx, 5, QTableWidgetItem(str(int(row.get("anomalies_updated") or 0)))
            )
            table.setItem(row_idx, 6, QTableWidgetItem(str(int(row.get("visits_updated") or 0)))
            )
            table.setItem(row_idx, 7, QTableWidgetItem(str(row.get("changed_by") or "")))
        table.resizeColumnsToContents()
        layout.addWidget(table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        _mark_button_variant(close_button, "secondary")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)
        fit_dialog_to_available_screen(self, preferred_width=960, preferred_height=620)


class MasterDataWidget(QWidget):
    def __init__(self, main_window, *, lazy_load: bool = False):
        super().__init__()
        self.main_window = main_window
        self._supplier_rows: list[dict] = []
        self._product_rows: list[dict] = []
        self._selected_supplier_id: str | None = None
        self._selected_product_id: str | None = None
        self._supplier_query_keyword = ""
        self._product_query_keyword = ""
        self._displayed_query_keyword = ""
        self._supplier_page = 1
        self._supplier_page_size = 13
        self._product_page = 1
        self._product_page_size = 13
        self._setup_ui()
        self._has_loaded = False
        if not lazy_load:
            self.refresh_data()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(ROOT_SECTION_SPACING)

        tabs_panel = QFrame()
        tabs_panel.setProperty("role", "panel")
        tabs_layout = QVBoxLayout(tabs_panel)
        tabs_layout.setContentsMargins(*PANEL_MARGINS)
        tabs_layout.setSpacing(8)

        self.inline_toolbar = QFrame()
        self.inline_toolbar.setObjectName("MasterInlineToolbar")
        self.inline_toolbar.setProperty("role", "masterToolbar")
        toolbar_outer = QVBoxLayout(self.inline_toolbar)
        toolbar_outer.setContentsMargins(0, 0, 0, 0)
        toolbar_outer.setSpacing(0)

        primary_row = QWidget()
        primary_row.setObjectName("MasterPrimaryRow")
        primary_layout = QHBoxLayout(primary_row)
        primary_layout.setContentsMargins(0, 0, 0, 0)
        primary_layout.setSpacing(TOOLBAR_ITEM_SPACING)

        self.query_input = QLineEdit()
        self.query_input.setMinimumWidth(220)
        self.query_input.setMaximumWidth(340)
        self.query_input.setPlaceholderText("輸入供應商名稱")
        self.query_input.setProperty("role", "masterQuery")
        self.query_input.returnPressed.connect(self._on_query_submitted)

        self.selection_status_label = QLabel("未選取供應商")
        self.selection_status_label.setObjectName("MasterSelectionStatus")
        self.selection_status_label.setProperty("role", "selectionStatus")
        self.selection_status_label.setToolTip("目前管理動作的選取對象")
        self.selection_status_label.setMinimumWidth(190)

        self.action_stack = QStackedWidget()
        self.action_stack.setObjectName("MasterActionStack")
        self.action_stack.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.action_stack.addWidget(self._build_supplier_actions_row())
        self.action_stack.addWidget(self._build_product_actions_row())

        primary_layout.addWidget(self.query_input)
        primary_layout.addWidget(self.selection_status_label)
        primary_layout.addStretch(1)
        primary_layout.addWidget(self.action_stack)

        toolbar_outer.addWidget(primary_row)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("MasterDataTabs")
        self.tabs.addTab(self._build_supplier_tab(), "供應商")
        self.tabs.addTab(self._build_product_tab(), "產品")
        apply_clickable_affordance(
            self.tabs.tabBar(),
            tooltip="切換供應商與產品清單",
        )

        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._last_tab_index = 0

        tabs_layout.addWidget(self.inline_toolbar)
        tabs_layout.addWidget(self.tabs)
        root.addWidget(tabs_panel, 1)
        self._on_tab_changed(self.tabs.currentIndex())

    def _create_toolbar_button(
        self,
        text: str,
        *,
        tooltip: str,
        variant: str,
        on_click,
    ) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("variant", variant)
        button.setToolTip(tooltip)
        apply_clickable_affordance(button, status_tip=tooltip)
        button.setMinimumHeight(TOOLBAR_CONTROL_MIN_HEIGHT)
        button.clicked.connect(on_click)
        return button

    def _focus_master_query(self) -> None:
        self.query_input.setFocus()
        self.query_input.selectAll()

    def _on_query_submitted(self) -> None:
        text = self.query_input.text().strip()
        if self.tabs.currentIndex() == 0:
            self._supplier_query_keyword = text
            self._supplier_page = 1
        else:
            self._product_query_keyword = text
            self._product_page = 1
        self._displayed_query_keyword = text
        self._render_supplier_table()
        self._render_product_table()

    def _filtered_supplier_rows(self) -> list[dict]:
        keyword = self._supplier_query_keyword.strip().lower()
        if not keyword:
            return list(self._supplier_rows)
        return [
            row
            for row in self._supplier_rows
            if keyword in str(row.get("supplier_name") or "").lower()
        ]

    def _filtered_product_rows(self) -> list[dict]:
        keyword = self._product_query_keyword.strip().lower()
        if not keyword:
            return list(self._product_rows)

        def matches(row: dict) -> bool:
            fields = (
                row.get("product_code"),
                row.get("product_name"),
                row.get("product_stage"),
                row.get("supplier_name"),
                row.get("secondary_supplier_name"),
            )
            return any(keyword in str(f or "").lower() for f in fields)

        return [row for row in self._product_rows if matches(row)]

    def _set_toggle_button_state(
        self, button: QPushButton, *, is_active: bool, entity: str
    ) -> None:
        action_text = "停用" if is_active else "啟用"
        button.setText(action_text)
        button.setToolTip(f"{action_text}{entity}")

    def _set_supplier_toggle_button_state(self, *, is_active: bool) -> None:
        self._set_toggle_button_state(
            self.btn_supplier_toggle, is_active=is_active, entity="供應商"
        )

    def _set_product_toggle_button_state(self, *, is_active: bool) -> None:
        self._set_toggle_button_state(
            self.btn_product_toggle, is_active=is_active, entity="產品"
        )

    def _build_supplier_actions_row(self) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        self.btn_supplier_create = self._create_toolbar_button(
            "新增",
            tooltip="新增供應商",
            variant="toolbarPrimary",
            on_click=self._create_supplier,
        )
        self.btn_supplier_update = self._create_toolbar_button(
            "更新",
            tooltip="更新供應商",
            variant="toolbarSecondary",
            on_click=self._update_supplier,
        )
        self.btn_supplier_toggle = self._create_toolbar_button(
            "停用",
            tooltip="停用供應商",
            variant="toolbarSecondary",
            on_click=self._toggle_supplier_active,
        )
        self.btn_supplier_delete = self._create_toolbar_button(
            "刪除",
            tooltip="刪除供應商",
            variant="toolbarSecondary",
            on_click=self._delete_supplier,
        )
        self.btn_supplier_delete_selected = self._create_toolbar_button(
            "刪選",
            tooltip="刪除選取供應商",
            variant="toolbarSecondary",
            on_click=self._delete_selected_suppliers,
        )
        self.btn_supplier_filter = self._create_toolbar_button(
            "篩選",
            tooltip="聚焦關鍵字篩選欄",
            variant="toolbarSecondary",
            on_click=self._focus_master_query,
        )
        self.btn_supplier_clear = self._create_toolbar_button(
            "清空",
            tooltip="清空供應商選取",
            variant="toolbarGhost",
            on_click=self._clear_supplier_form,
        )

        row_layout.addWidget(self.btn_supplier_create)
        row_layout.addWidget(self.btn_supplier_update)
        row_layout.addWidget(self.btn_supplier_toggle)
        row_layout.addWidget(self.btn_supplier_delete)
        row_layout.addWidget(self.btn_supplier_delete_selected)
        row_layout.addWidget(self.btn_supplier_filter)
        row_layout.addSpacing(16)
        row_layout.addWidget(self.btn_supplier_clear)
        return row

    def _build_product_actions_row(self) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        self.btn_product_create = self._create_toolbar_button(
            "新增",
            tooltip="新增產品",
            variant="toolbarPrimary",
            on_click=self._create_product,
        )
        self.btn_product_update = self._create_toolbar_button(
            "更新",
            tooltip="更新產品",
            variant="toolbarSecondary",
            on_click=self._update_product,
        )
        self.btn_product_toggle = self._create_toolbar_button(
            "停用",
            tooltip="停用產品",
            variant="toolbarSecondary",
            on_click=self._toggle_product_active,
        )
        self.btn_product_delete = self._create_toolbar_button(
            "刪除",
            tooltip="刪除產品",
            variant="toolbarSecondary",
            on_click=self._delete_product,
        )
        self.btn_product_stage_logs = self._create_toolbar_button(
            "紀錄",
            tooltip="查詢產品階段異動紀錄",
            variant="toolbarSecondary",
            on_click=self._show_product_stage_logs,
        )
        self.btn_product_import = self._create_toolbar_button(
            "匯入",
            tooltip="從 Excel / ERP 匯出檔匯入共用產品與供應商主檔",
            variant="toolbarSecondary",
            on_click=self._import_products_from_excel,
        )
        self.btn_product_filter = self._create_toolbar_button(
            "篩選",
            tooltip="聚焦關鍵字篩選欄",
            variant="toolbarSecondary",
            on_click=self._focus_master_query,
        )
        self.btn_product_clear = self._create_toolbar_button(
            "清空",
            tooltip="清空產品選取",
            variant="toolbarGhost",
            on_click=self._clear_product_form,
        )

        row_layout.addWidget(self.btn_product_create)
        row_layout.addWidget(self.btn_product_update)
        row_layout.addWidget(self.btn_product_toggle)
        row_layout.addWidget(self.btn_product_delete)
        row_layout.addWidget(self.btn_product_stage_logs)
        row_layout.addWidget(self.btn_product_import)
        row_layout.addWidget(self.btn_product_filter)
        row_layout.addSpacing(16)
        row_layout.addWidget(self.btn_product_clear)
        return row

    def _build_supplier_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, TAB_CONTENT_TOP_MARGIN, 0, 0)
        layout.setSpacing(8)

        self.supplier_table = QTableWidget()
        self.supplier_table.setColumnCount(6)
        self.supplier_table.setHorizontalHeaderLabels(
            ["供應商", "聯絡人", "部門", "電子郵件", "電話/行動", "狀態"]
        )
        style_table(self.supplier_table, single_selection=False)
        self.supplier_table.horizontalHeader().setStretchLastSection(True)
        apply_table_action_affordance(
            self.supplier_table,
            "點擊供應商列開啟管理動作；Ctrl/Shift 可多選後批次刪除",
        )
        self.supplier_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.supplier_table.itemSelectionChanged.connect(self._on_supplier_selected)
        self.supplier_table.cellClicked.connect(self._on_supplier_table_clicked)
        layout.addWidget(self.supplier_table, 1)

        self.supplier_pagination = PaginationBar(
            on_page_changed=self._on_supplier_page_changed,
            on_page_size_changed=self._on_supplier_page_size_changed,
            default_page_size=self._supplier_page_size,
        )
        layout.addWidget(self.supplier_pagination)
        return panel

    def _build_product_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, TAB_CONTENT_TOP_MARGIN, 0, 0)
        layout.setSpacing(8)

        self.product_table = QTableWidget()
        self.product_table.setColumnCount(6)
        self.product_table.setHorizontalHeaderLabels(
            ["料號", "品名", "階段", "主供應商", "次要供應商", "狀態"]
        )
        style_table(self.product_table)
        self.product_table.horizontalHeader().setStretchLastSection(True)
        apply_table_action_affordance(
            self.product_table,
            "點擊產品列開啟編輯、停用、刪除或階段紀錄動作",
        )
        self.product_table.itemSelectionChanged.connect(self._on_product_selected)
        self.product_table.cellClicked.connect(self._on_product_table_clicked)
        layout.addWidget(self.product_table, 1)

        self.product_pagination = PaginationBar(
            on_page_changed=self._on_product_page_changed,
            on_page_size_changed=self._on_product_page_size_changed,
            default_page_size=self._product_page_size,
        )
        layout.addWidget(self.product_pagination)
        return panel

    def _on_tab_changed(self, index: int) -> None:
        current_text = self.query_input.text().strip()
        if current_text != self._displayed_query_keyword:
            if self._last_tab_index == 0:
                self._supplier_query_keyword = current_text
            else:
                self._product_query_keyword = current_text

        self._last_tab_index = index
        tab_index = 0 if index <= 0 else 1
        self.action_stack.setCurrentIndex(tab_index)
        if index == 0:
            self.query_input.setPlaceholderText("輸入供應商名稱")
            next_keyword = self._supplier_query_keyword
        else:
            self.query_input.setPlaceholderText("輸入料號、品名或供應商")
            next_keyword = self._product_query_keyword
        self.query_input.setText(next_keyword)
        self._displayed_query_keyword = next_keyword

        # Reset page to 1 when switching tabs or query
        # Actually, let's keep it but for simplicity when keyword is explicitly changed we reset.
        # But this method is just tab change.
        try:
            self._render_supplier_table()
            self._render_product_table()
            self._sync_action_buttons()
        except RuntimeError:
            # During Qt teardown, tab signals may fire after child widgets are deleted.
            return

    def refresh_data(self):
        self._has_loaded = True
        self._supplier_rows = event_service.list_suppliers(include_inactive=True)
        self._product_rows = event_service.list_products(include_inactive=True)
        self._render_supplier_table()
        self._render_product_table()
        self._sync_action_buttons()
        self._on_tab_changed(self.tabs.currentIndex())

    def _render_supplier_table(self):
        selected_supplier_id = self._selected_supplier_id
        visible_rows = self._filtered_supplier_rows()
        total_items = len(visible_rows)
        
        start = (self._supplier_page - 1) * self._supplier_page_size
        end = start + self._supplier_page_size
        page_rows = visible_rows[start:end]

        self.supplier_table.setRowCount(0)
        selected_row_index: int | None = None
        for idx, row in enumerate(page_rows):
            self.supplier_table.insertRow(idx)
            status_text = "啟用" if row["is_active"] else "停用"
            self.supplier_table.setItem(idx, 0, QTableWidgetItem(row["supplier_name"]))
            self.supplier_table.setItem(idx, 1, QTableWidgetItem(row.get("contact_name", "")))
            self.supplier_table.setItem(idx, 2, QTableWidgetItem(row.get("department", "")))
            self.supplier_table.setItem(idx, 3, QTableWidgetItem(row.get("contact_email", "")))
            self.supplier_table.setItem(idx, 4, QTableWidgetItem(row.get("phone", "")))
            status_item = create_status_item(status_text)
            self.supplier_table.setItem(idx, 5, status_item)
            self.supplier_table.item(idx, 0).setData(Qt.ItemDataRole.UserRole, row["id"])
            if row["id"] == selected_supplier_id:
                selected_row_index = idx

        self.supplier_pagination.set_state(
            total_items=total_items,
            current_page=self._supplier_page,
            page_size=self._supplier_page_size,
        )

        if selected_supplier_id and selected_row_index is None:
            # If the selected item is not on the current page, we keep the ID but clear selection
            self.supplier_table.clearSelection()
            # self._set_supplier_toggle_button_state(is_active=True) # Keep current state if possible
        elif selected_row_index is not None:
            self._select_single_row(self.supplier_table, selected_row_index)

    def _render_product_table(self):
        selected_product_id = self._selected_product_id
        visible_rows = self._filtered_product_rows()
        total_items = len(visible_rows)

        start = (self._product_page - 1) * self._product_page_size
        end = start + self._product_page_size
        page_rows = visible_rows[start:end]

        self.product_table.setRowCount(0)
        selected_row_index: int | None = None
        for idx, row in enumerate(page_rows):
            self.product_table.insertRow(idx)
            status_text = "啟用" if row["is_active"] else "停用"
            product_stage = normalize_product_stage_ui(row.get("product_stage"))
            primary_supplier_text = row.get("supplier_name") or "（未指定）"
            secondary_supplier_text = row.get("secondary_supplier_name") or "（未指定）"
            self.product_table.setItem(idx, 0, QTableWidgetItem(row["product_code"]))
            self.product_table.setItem(idx, 1, QTableWidgetItem(row["product_name"]))
            self.product_table.setItem(idx, 2, QTableWidgetItem(product_stage))
            self.product_table.setItem(idx, 3, QTableWidgetItem(primary_supplier_text))
            self.product_table.setItem(idx, 4, QTableWidgetItem(secondary_supplier_text))
            status_item = create_status_item(status_text)
            self.product_table.setItem(idx, 5, status_item)
            self.product_table.item(idx, 0).setData(Qt.ItemDataRole.UserRole, row["id"])
            if row["id"] == selected_product_id:
                selected_row_index = idx

        self.product_pagination.set_state(
            total_items=total_items,
            current_page=self._product_page,
            page_size=self._product_page_size,
        )

        if selected_product_id and selected_row_index is None:
            self.product_table.clearSelection()
        elif selected_row_index is not None:
            self._select_single_row(self.product_table, selected_row_index)

    def _sync_action_buttons(self):
        supplier_selection_count = len(self._selected_table_ids(self.supplier_table))
        has_supplier = supplier_selection_count > 0
        has_single_supplier = supplier_selection_count == 1
        has_product = self._selected_product_id is not None
        self.btn_supplier_update.setEnabled(has_single_supplier)
        self.btn_supplier_toggle.setEnabled(has_single_supplier)
        self.btn_supplier_delete.setEnabled(has_supplier)
        self.btn_supplier_delete_selected.setEnabled(has_supplier)
        self.btn_product_update.setEnabled(has_product)
        self.btn_product_toggle.setEnabled(has_product)
        self.btn_product_delete.setEnabled(has_product)
        self.btn_product_stage_logs.setEnabled(has_product)
        self._sync_selection_status()

    def _sync_selection_status(self) -> None:
        if not hasattr(self, "selection_status_label"):
            return
        if self.tabs.currentIndex() == 0:
            selected_ids = self._selected_table_ids(self.supplier_table)
            if not selected_ids:
                text = "未選取供應商"
            elif len(selected_ids) == 1:
                text = f"已選取供應商：{self._supplier_label(selected_ids[0])}"
            else:
                text = f"已選取供應商：{len(selected_ids)} 筆"
        else:
            if self._selected_product_id:
                text = f"已選取產品：{self._product_label(self._selected_product_id)}"
            else:
                text = "未選取產品"
        self.selection_status_label.setText(text)

    def _find_supplier_row(self, supplier_id: str | None) -> dict | None:
        if not supplier_id:
            return None
        for row in self._supplier_rows:
            if row["id"] == supplier_id:
                return row
        return None

    def _find_product_row(self, product_id: str | None) -> dict | None:
        if not product_id:
            return None
        for row in self._product_rows:
            if row["id"] == product_id:
                return row
        return None

    def _selected_table_ids(self, table: QTableWidget) -> list[str]:
        indexes = table.selectionModel().selectedRows() if table.selectionModel() else []
        selected_ids: list[str] = []
        seen: set[str] = set()
        for model_index in sorted(indexes, key=lambda idx: idx.row()):
            item = table.item(model_index.row(), 0)
            if item is None:
                continue
            value = item.data(Qt.ItemDataRole.UserRole)
            if not value:
                continue
            item_id = str(value)
            if item_id in seen:
                continue
            seen.add(item_id)
            selected_ids.append(item_id)
        return selected_ids

    def _selected_table_id(self, table: QTableWidget) -> str | None:
        selected_ids = self._selected_table_ids(table)
        if not selected_ids:
            return None
        return selected_ids[0]

    def _table_menu_pos(self, table: QTableWidget, row_idx: int):
        index = table.model().index(row_idx, 0)
        rect = table.visualRect(index)
        if rect.isValid():
            return table.viewport().mapToGlobal(rect.center())
        return table.mapToGlobal(table.rect().center())

    def _select_single_row(self, table: QTableWidget, row_idx: int):
        table.clearSelection()
        table.selectRow(row_idx)
        table.setCurrentCell(row_idx, 0)

    def _on_supplier_page_changed(self, page_no: int):
        self._supplier_page = page_no
        self._render_supplier_table()

    def _on_supplier_page_size_changed(self, page_size: int):
        self._supplier_page_size = page_size
        self._supplier_page = 1
        self._render_supplier_table()

    def _on_product_page_changed(self, page_no: int):
        self._product_page = page_no
        self._render_product_table()

    def _on_product_page_size_changed(self, page_size: int):
        self._product_page_size = page_size
        self._product_page = 1
        self._render_product_table()

    def _on_supplier_table_clicked(self, row_idx: int, _column_idx: int):
        modifiers = QApplication.keyboardModifiers()
        if modifiers & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            return
        item = self.supplier_table.item(row_idx, 0)
        if item is None:
            return
        supplier_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        row = self._find_supplier_row(supplier_id)
        if row is None:
            return
        self._select_single_row(self.supplier_table, row_idx)

        menu = QMenu(self)
        action_edit = menu.addAction("編輯")
        action_toggle = menu.addAction("停用" if row["is_active"] else "啟用")
        action_delete = menu.addAction("刪除")
        selected = menu.exec(self._table_menu_pos(self.supplier_table, row_idx))
        if selected is action_edit:
            self._update_supplier()
        elif selected is action_toggle:
            self._toggle_supplier_active()
        elif selected is action_delete:
            self._delete_supplier()

    def _on_product_table_clicked(self, row_idx: int, _column_idx: int):
        modifiers = QApplication.keyboardModifiers()
        if modifiers & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            return
        item = self.product_table.item(row_idx, 0)
        if item is None:
            return
        product_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        row = self._find_product_row(product_id)
        if row is None:
            return
        self._select_single_row(self.product_table, row_idx)

        menu = QMenu(self)
        action_edit = menu.addAction("編輯")
        action_toggle = menu.addAction("停用" if row["is_active"] else "啟用")
        action_delete = menu.addAction("刪除")
        action_logs = menu.addAction("階段紀錄")
        selected = menu.exec(self._table_menu_pos(self.product_table, row_idx))
        if selected is action_edit:
            self._update_product()
        elif selected is action_toggle:
            self._toggle_product_active()
        elif selected is action_delete:
            self._delete_product()
        elif selected is action_logs:
            self._show_product_stage_logs()

    def _on_supplier_selected(self):
        selected_ids = self._selected_table_ids(self.supplier_table)
        self._selected_supplier_id = selected_ids[0] if selected_ids else None
        row = (
            self._find_supplier_row(self._selected_supplier_id)
            if len(selected_ids) == 1
            else None
        )
        if row is not None:
            self._set_supplier_toggle_button_state(is_active=bool(row["is_active"]))
        else:
            self._set_supplier_toggle_button_state(is_active=True)
        self._sync_action_buttons()

    def _on_product_selected(self):
        self._selected_product_id = self._selected_table_id(self.product_table)
        row = self._find_product_row(self._selected_product_id)
        if row:
            self._set_product_toggle_button_state(is_active=bool(row["is_active"]))
        else:
            self._set_product_toggle_button_state(is_active=True)
        self._sync_action_buttons()

    def _clear_supplier_form(self):
        self._selected_supplier_id = None
        self.supplier_table.clearSelection()
        self._set_supplier_toggle_button_state(is_active=True)
        self._sync_action_buttons()

    def _clear_product_form(self):
        self._selected_product_id = None
        self.product_table.clearSelection()
        self._set_product_toggle_button_state(is_active=True)
        self._sync_action_buttons()

    def _open_supplier_dialog(
        self, *, initial_data: dict | None, is_edit: bool
    ) -> dict | None:
        dialog = SupplierFormDialog(self, initial_data=initial_data, is_edit=is_edit)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.payload()

    def _open_product_dialog(
        self, *, initial_data: dict | None, is_edit: bool
    ) -> dict | None:
        dialog = ProductFormDialog(
            self._supplier_rows,
            self,
            initial_data=initial_data,
            is_edit=is_edit,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.payload()

    def _create_supplier(self):
        payload = self._open_supplier_dialog(initial_data=None, is_edit=False)
        if payload is None:
            return
        try:
            event_service.create_supplier(payload)
            self.main_window.refresh_all_views()
            self._clear_supplier_form()
            QMessageBox.information(self, "成功", localize_popup_message("供應商已建立"))
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", localize_exception(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"建立供應商失敗：{localize_exception(exc)}"),
            )

    def _update_supplier(self):
        if not self._selected_supplier_id:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇供應商"))
            return
        row = self._find_supplier_row(self._selected_supplier_id)
        if row is None:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇供應商"))
            return

        payload = self._open_supplier_dialog(initial_data=row, is_edit=True)
        if payload is None:
            return
        try:
            event_service.update_supplier(self._selected_supplier_id, payload)
            self.main_window.refresh_all_views()
            QMessageBox.information(self, "成功", localize_popup_message("供應商已更新"))
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", localize_exception(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"更新供應商失敗：{localize_exception(exc)}"),
            )

    def _toggle_supplier_active(self):
        row = self._find_supplier_row(self._selected_supplier_id)
        if not row:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇供應商"))
            return
        target_active = not bool(row.get("is_active"))
        action_text = "啟用" if target_active else "停用"
        supplier_label = self._supplier_label(str(row.get("id") or ""))
        confirm = QMessageBox.question(
            self,
            f"確認{action_text}",
            localize_popup_message(f"確定要{action_text}供應商「{supplier_label}」？"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            event_service.set_supplier_active(row["id"], target_active)
            self.main_window.refresh_all_views()
            QMessageBox.information(
                self, "成功", localize_popup_message(f"供應商已{action_text}")
            )
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", localize_exception(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"{action_text}供應商失敗：{localize_exception(exc)}"),
            )

    def _supplier_label(self, supplier_id: str) -> str:
        row = self._find_supplier_row(supplier_id)
        if row is not None:
            return str(row.get("supplier_name") or supplier_id)
        return supplier_id or "（空白ID）"

    def _product_label(self, product_id: str) -> str:
        row = self._find_product_row(product_id)
        if row is not None:
            code = str(row.get("product_code") or "").strip()
            name = str(row.get("product_name") or "").strip()
            if code and name:
                return f"[{code}] {name}"
            return name or code or product_id
        return product_id or "（空白ID）"

    def _show_product_stage_logs(self):
        product_id = self._selected_product_id
        if not product_id:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇產品"))
            return
        try:
            logs = event_service.list_product_stage_change_logs(product_id=product_id, limit=200)
            dialog = ProductStageLogDialog(self._product_label(product_id), logs, self)
            dialog.exec()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"載入階段異動紀錄失敗：{localize_exception(exc)}"),
            )

    def _import_products_from_excel(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "匯入共用產品主檔",
            "",
            "Excel Files (*.xlsx)",
        )
        if not file_path:
            return
        try:
            with get_connection() as conn:
                preview = master_import_service.preview_product_master_import(
                    conn,
                    Path(file_path),
                )
                if preview.error_count:
                    batch_id = master_import_service.record_product_master_import_rejection(
                        conn,
                        preview,
                        source_file=Path(file_path),
                    )
                    error_lines = list(preview.file_errors)
                    error_lines.extend(
                        f"第 {row.row_number} 列：{row.message}"
                        for row in preview.rows
                        if row.is_error
                    )
                    if len(error_lines) > 10:
                        error_lines = [
                            *error_lines[:10],
                            f"... 尚有 {preview.error_count - 10} 項錯誤未列出",
                        ]
                    QMessageBox.warning(
                        self,
                        "匯入預覽失敗",
                        localize_popup_message(
                            "\n".join(
                                [
                                    f"批次：{batch_id}",
                                    "未寫入 suppliers/products、事件或倉庫不合格品資料。",
                                    "",
                                    *error_lines,
                                ]
                            )
                        ),
                    )
                    return
                if not preview.has_writes:
                    result = master_import_service.apply_product_master_import(
                        conn,
                        preview,
                        source_file=Path(file_path),
                    )
                    QMessageBox.information(
                        self,
                        "匯入預覽",
                        localize_popup_message(
                            "共用產品與供應商主檔已一致，沒有需要匯入的資料。\n"
                            f"批次：{result.batch_id}"
                        ),
                    )
                    return

                message = (
                    f"新增產品：{preview.add_count} 筆\n"
                    f"更新產品：{preview.update_count} 筆\n"
                    f"新增供應商：{preview.supplier_create_count} 筆\n"
                    f"略過：{preview.skipped_count} 筆\n\n"
                    "本匯入只寫入 suppliers/products 共用主檔，"
                    "不寫入訪廠缺失、正式異常或倉庫不合格品資料。\n\n"
                    "確認匯入？"
                )
                confirm = QMessageBox.question(
                    self,
                    "確認匯入",
                    localize_popup_message(message),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if confirm != QMessageBox.StandardButton.Yes:
                    return
                result = master_import_service.apply_product_master_import(
                    conn,
                    preview,
                    source_file=Path(file_path),
                )

            self.refresh_data()
            self.main_window.refresh_all_views()
            backup_text = (
                f"\n備份：{result.backup_path}"
                if result.backup_path is not None
                else ""
            )
            QMessageBox.information(
                self,
                "匯入完成",
                localize_popup_message(
                    f"新增產品：{result.added_count} 筆\n"
                    f"更新產品：{result.updated_count} 筆\n"
                    f"新增供應商：{result.supplier_created_count} 筆\n"
                    f"略過：{result.skipped_count} 筆"
                    f"{backup_text}\n"
                    f"批次：{result.batch_id}"
                ),
            )
        except (ValueError, master_import_service.MasterImportError) as exc:
            QMessageBox.warning(self, "匯入失敗", localize_exception(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"匯入產品主檔失敗：{localize_exception(exc)}"),
            )

    def _delete_supplier(self):
        selected_ids = self._selected_table_ids(self.supplier_table)
        if not selected_ids:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇供應商"))
            return
        supplier_id = selected_ids[0]
        supplier_label = self._supplier_label(supplier_id)
        confirm = QMessageBox.question(
            self,
            "確認刪除",
            localize_popup_message(f"確定要刪除供應商「{supplier_label}」？\n此操作無法復原。"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            event_service.delete_supplier(supplier_id)
            self.main_window.refresh_all_views()
            self._clear_supplier_form()
            QMessageBox.information(
                self,
                "成功",
                localize_popup_message(f"供應商「{supplier_label}」已刪除"),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", localize_exception(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"刪除供應商失敗：{localize_exception(exc)}"),
            )

    def _delete_selected_suppliers(self):
        selected_ids = self._selected_table_ids(self.supplier_table)
        if not selected_ids:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇供應商"))
            return
        preview_labels = [self._supplier_label(item_id) for item_id in selected_ids[:5]]
        preview_text = "、".join(preview_labels)
        if len(selected_ids) > 5:
            preview_text = f"{preview_text} ... 等 {len(selected_ids)} 筆"
        confirm = QMessageBox.question(
            self,
            "確認刪除",
            localize_popup_message(
                f"確定要刪除選取的 {len(selected_ids)} 筆供應商？\n{preview_text}\n此操作無法復原。"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        keyword, ok = QInputDialog.getText(
            self,
            "二次確認",
            localize_popup_message(
                f"刪除摘要：共 {len(selected_ids)} 筆\n{preview_text}\n\n請輸入 DELETE 以確認刪除。"
            ),
        )
        if not ok:
            return
        if keyword.strip().upper() != "DELETE":
            QMessageBox.warning(
                self,
                "已取消",
                localize_popup_message("未輸入 DELETE，已取消批次刪除。"),
            )
            return
        try:
            result = event_service.delete_suppliers(selected_ids)
            deleted = list(result.get("deleted", []))
            failed = list(result.get("failed", []))
            self.main_window.refresh_all_views()
            self._clear_supplier_form()

            if failed:
                failed_lines: list[str] = []
                for item in failed[:10]:
                    failed_id = str(item.get("id") or "")
                    failed_reason = localize_popup_message(str(item.get("reason") or ""))
                    failed_lines.append(
                        f"- {self._supplier_label(failed_id)}：{failed_reason}"
                    )
                if len(failed) > 10:
                    failed_lines.append(f"... 尚有 {len(failed) - 10} 筆未列出")
                detail = "\n".join(failed_lines)
                if deleted:
                    QMessageBox.warning(
                        self,
                        "部分成功",
                        localize_popup_message(
                            f"已刪除 {len(deleted)} 筆，{len(failed)} 筆刪除失敗。\n\n{detail}"
                        ),
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "刪除失敗",
                        localize_popup_message(f"共 {len(failed)} 筆刪除失敗。\n\n{detail}"),
                    )
            else:
                QMessageBox.information(
                    self,
                    "成功",
                    localize_popup_message(f"已刪除 {len(deleted)} 筆供應商"),
                )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"批次刪除供應商失敗：{localize_exception(exc)}"),
            )

    def _create_product(self):
        payload = self._open_product_dialog(initial_data=None, is_edit=False)
        if payload is None:
            return
        try:
            event_service.create_product(payload)
            self.main_window.refresh_all_views()
            self._clear_product_form()
            QMessageBox.information(self, "成功", localize_popup_message("產品已建立"))
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", localize_exception(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"建立產品失敗：{localize_exception(exc)}"),
            )

    def _update_product(self):
        if not self._selected_product_id:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇產品"))
            return
        row = self._find_product_row(self._selected_product_id)
        if row is None:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇產品"))
            return
        payload = self._open_product_dialog(initial_data=row, is_edit=True)
        if payload is None:
            return
        try:
            event_service.update_product(self._selected_product_id, payload)
            self.main_window.refresh_all_views()
            QMessageBox.information(self, "成功", localize_popup_message("產品已更新"))
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", localize_exception(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"更新產品失敗：{localize_exception(exc)}"),
            )

    def _toggle_product_active(self):
        row = self._find_product_row(self._selected_product_id)
        if not row:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇產品"))
            return
        target_active = not bool(row.get("is_active"))
        action_text = "啟用" if target_active else "停用"
        product_label = self._product_label(str(row.get("id") or ""))
        confirm = QMessageBox.question(
            self,
            f"確認{action_text}",
            localize_popup_message(f"確定要{action_text}產品「{product_label}」？"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            event_service.set_product_active(row["id"], target_active)
            self.main_window.refresh_all_views()
            QMessageBox.information(
                self, "成功", localize_popup_message(f"產品已{action_text}")
            )
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", localize_exception(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"{action_text}產品失敗：{localize_exception(exc)}"),
            )

    def _delete_product(self):
        product_id = self._selected_product_id
        if not product_id:
            QMessageBox.warning(self, "提示", localize_popup_message("請先選擇產品"))
            return
        product_label = self._product_label(product_id)
        confirm = QMessageBox.question(
            self,
            "確認刪除",
            localize_popup_message(f"確定要刪除產品「{product_label}」？\n此操作無法復原。"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            event_service.delete_product(product_id)
            self.main_window.refresh_all_views()
            self._clear_product_form()
            QMessageBox.information(
                self,
                "成功",
                localize_popup_message(f"產品「{product_label}」已刪除"),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", localize_exception(exc))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"刪除產品失敗：{localize_exception(exc)}"),
            )
