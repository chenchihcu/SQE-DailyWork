from __future__ import annotations

import sqlite3
from collections.abc import Callable

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from ui.layout_constants import DIALOG_OUTER_MARGINS
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFrame,
)

from ncr.db import crud
from ncr.ui.supplier_combo_utils import (
    SUPPLIER_CATEGORY_FORMAL,
    SUPPLIER_CATEGORY_OUTSOURCE,
    apply_supplier_exclusion_lock,
    load_supplier_names_by_category,
)
from ncr.models.defect import (
    CATEGORY_OPTIONS,
    DISPOSITION_OPTIONS,
    RESPONSIBILITY_OPTIONS,
    RETURN_SLIP_TYPE_OPTIONS,
    STATUS_OPTIONS,
)
from ncr.models.labels import (
    HINT_SAVE_SHORTCUT,
    LABEL_CATEGORY,
    LABEL_DEFECT_DESC,
    LABEL_DEFECT_NO,
    LABEL_DISPOSITION,
    LABEL_EVENT_DATE,
    LABEL_ITEM_NO,
    LABEL_OUTSOURCE_SUPPLIER_NAME,
    LABEL_PRODUCT_NAME,
    LABEL_RESPONSIBILITY,
    LABEL_RETURN_SLIP_TYPE,
    LABEL_QTY,
    LABEL_STATUS,
    LABEL_SUPPLIER_NAME,
    LABEL_WORK_ORDER_NO,
    LABEL_INTERNAL_WORK_ORDER_NO,
    LABEL_TRANSFER_SLIP_NO,
    MSG_SAVE_FAILED,
    MSG_SAVE_SUCCESS,
    MSG_SAVING,
    MSG_UPDATE_SUCCESS,
    VALIDATION_ITEM_NO_NOT_FOUND,
    PLACEHOLDER_DEFECT_DESC,
    PLACEHOLDER_OUTSOURCE_SUPPLIER,
    HEADER_CREATED_AT,
)
from ncr.services import defect_service, product_service
from ncr.ui.ui_style import (
    DATE_FIELD_MIN_WIDTH,
    DEFECT_FORM_CONTENT_MARGINS,
    DIALOG_ACTION_BUTTON_MIN_WIDTH,
    FIELD_SPACING_Y,
    FORM_COMPACT_FIELD_MIN_WIDTH,
    FORM_COMPACT_LABEL_WIDTH,
    FORM_TWO_COLUMN_SPACING,
    INPUT_HEIGHT,
    QUICK_ADD_BUTTON_MIN_WIDTH,
    SECTION_SPACING,
    STATUS_TIMEOUT_ERROR,
    STATUS_TIMEOUT_PERSIST,
    STATUS_TIMEOUT_SUCCESS,
    add_labeled_field,
    apply_button_icon,
    apply_form_inputs,
    create_form_grid,
    create_page_shell,
    create_section_card,
    create_section_title_with_icon,
    fit_window_to_available_screen,
    make_hint_label,
    make_notice_label,
    set_button_role,
    format_datetime,
)


def _connect_dirty_tracking_signals(
    fields: "DefectFieldsWidget", on_dirty: Callable[..., None]
) -> None:
    fields.event_date_edit.dateChanged.connect(on_dirty)
    fields.return_slip_type_combo.currentTextChanged.connect(on_dirty)
    fields.work_order_input.textChanged.connect(on_dirty)
    fields.internal_work_order_input.textChanged.connect(on_dirty)
    fields.transfer_slip_input.textChanged.connect(on_dirty)
    fields.category_combo.currentTextChanged.connect(on_dirty)
    fields.item_no_input.currentTextChanged.connect(on_dirty)
    fields.product_name_input.textChanged.connect(on_dirty)
    fields.qty_spin.valueChanged.connect(on_dirty)
    fields.supplier_combo.currentTextChanged.connect(on_dirty)
    fields.outsource_supplier_combo.currentTextChanged.connect(on_dirty)
    fields.defect_desc_input.textChanged.connect(on_dirty)
    fields.status_combo.currentTextChanged.connect(on_dirty)
    fields.disposition_combo.currentTextChanged.connect(on_dirty)
    fields.responsibility_combo.currentTextChanged.connect(on_dirty)


class DirtyTrackingMixin:
    def _mark_dirty(self, *_args: object) -> None:
        if self._track_changes:
            self._is_dirty = True

    def _mark_clean(self) -> None:
        self._is_dirty = False

    def _set_save_busy_state(self, busy: bool) -> None:
        self._is_saving = busy


class QuickProductCreateDialog(QDialog):
    def __init__(
        self,
        conn: sqlite3.Connection,
        item_no: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.conn = conn
        self.created_product_name = ""
        self.setWindowTitle("快速建立產品")
        fit_window_to_available_screen(self, 420, 220, enable_size_grip=True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        layout.setSpacing(FIELD_SPACING_Y)

        form_grid = create_form_grid(field_count=1)
        self.item_no_input = QLineEdit(item_no.strip())
        self.item_no_input.setReadOnly(True)
        self.product_name_input = QLineEdit()
        self.product_name_input.setPlaceholderText("輸入產品名稱")
        apply_form_inputs([self.item_no_input, self.product_name_input])
        add_labeled_field(form_grid, 0, LABEL_ITEM_NO, self.item_no_input)
        add_labeled_field(form_grid, 1, LABEL_PRODUCT_NAME, self.product_name_input)
        layout.addLayout(form_grid)

        self.feedback_label = make_notice_label("", role="warningHint")
        layout.addWidget(self.feedback_label)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_button = QPushButton("取消")
        self.save_button = QPushButton("建立產品")
        self.cancel_button.setMinimumWidth(DIALOG_ACTION_BUTTON_MIN_WIDTH)
        self.save_button.setMinimumWidth(DIALOG_ACTION_BUTTON_MIN_WIDTH)
        set_button_role(self.cancel_button, "secondary")
        set_button_role(self.save_button, "primary")
        apply_button_icon(self.cancel_button, "cancel")
        apply_button_icon(self.save_button, "save")
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.create_product)
        actions.addWidget(self.save_button)
        actions.addWidget(self.cancel_button)
        layout.addLayout(actions)

    def _show_error(self, message: str) -> None:
        self.feedback_label.setText(message)
        self.feedback_label.setVisible(True)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.product_name_input.text().strip():
            reply = QMessageBox.question(
                self,
                "放棄輸入",
                "產品名稱尚未儲存，確定要關閉嗎？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        super().closeEvent(event)

    def create_product(self) -> bool:
        item_no = self.item_no_input.text().strip()
        product_name = self.product_name_input.text().strip()
        if not item_no:
            self._show_error("料號不可空白。")
            return False
        if not product_name:
            self._show_error("產品名稱不可空白。")
            return False
        try:
            product_service.create_product(
                self.conn,
                {"item_no": item_no, "product_name": product_name},
            )
        except ValueError as exc:
            self._show_error(str(exc))
            return False
        except sqlite3.Error as exc:
            self._show_error(f"資料庫錯誤：{exc}")
            return False
        self.created_product_name = product_name
        self.accept()
        return True


class DefectFieldsWidget(QWidget):
    product_created = Signal(str, str)

    def __init__(
        self,
        conn: sqlite3.Connection,
        parent: QWidget | None = None,
        *,
        allow_quick_product_create: bool = True,
    ):
        super().__init__(parent)
        self.conn = conn
        self.allow_quick_product_create = allow_quick_product_create
        self._product_name_by_item_no: dict[str, str] = {}
        self._build_ui()
        self.reset_fields()
        self.refresh_product_options()
        self.refresh_supplier_options()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(SECTION_SPACING)

        self.event_date_edit = QDateEdit()
        self.event_date_edit.setCalendarPopup(True)
        self.event_date_edit.setDisplayFormat("yyyy-MM-dd")
        # 確保 yyyy-MM-dd 與日曆鈕在 1.5x DPI 不被裁成 yyyy-MM
        self.event_date_edit.setMinimumWidth(DATE_FIELD_MIN_WIDTH)

        self.return_slip_type_combo = QComboBox()
        self.return_slip_type_combo.addItem("")
        self.return_slip_type_combo.addItems(RETURN_SLIP_TYPE_OPTIONS)

        self.work_order_input = QLineEdit()
        self.internal_work_order_input = QLineEdit()
        self.transfer_slip_input = QLineEdit()
        self.category_combo = QComboBox()
        self.category_combo.addItems(CATEGORY_OPTIONS)

        self.item_no_input = QComboBox()
        self.item_no_input.setEditable(True)
        self.item_no_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.item_no_input.setMaxVisibleItems(16)
        self.item_no_input.setToolTip("可輸入或從資料庫產品清單選取料號")
        line_edit = self.item_no_input.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText("輸入或選取料號")
            line_edit.setClearButtonEnabled(True)
        self.product_name_input = QLineEdit()
        self.product_name_input.setReadOnly(True)
        self.product_name_input.setPlaceholderText("由料號自動帶出")
        self.quick_add_product_btn = QPushButton("+ 建立")
        self.quick_add_product_btn.setObjectName("quickAddProductButton")
        self.quick_add_product_btn.setToolTip("快速建立目前料號的產品名稱")
        self.quick_add_product_btn.setAccessibleName("快速建立產品名稱")
        self.quick_add_product_btn.setVisible(False)
        self.quick_add_product_btn.setMinimumWidth(QUICK_ADD_BUTTON_MIN_WIDTH)
        set_button_role(self.quick_add_product_btn, "utility")
        self.quick_add_product_btn.clicked.connect(self.open_quick_product_create_dialog)

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 1_000_000)
        self.qty_spin.setMinimumHeight(INPUT_HEIGHT)
        self.qty_spin.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)

        self.supplier_combo = QComboBox()
        self.supplier_combo.setEditable(True)

        self.outsource_supplier_combo = QComboBox()
        self.outsource_supplier_combo.setEditable(False)
        self.outsource_supplier_combo.setPlaceholderText(PLACEHOLDER_OUTSOURCE_SUPPLIER)
        self.supplier_combo.currentTextChanged.connect(self._on_supplier_changed)
        self.outsource_supplier_combo.currentTextChanged.connect(
            self._on_outsource_supplier_changed
        )
        self.item_no_input.currentTextChanged.connect(self._on_item_no_changed)

        self.defect_desc_input = QTextEdit()
        self.defect_desc_input.setPlaceholderText(PLACEHOLDER_DEFECT_DESC)
        self._set_defect_desc_height()

        self.status_combo = QComboBox()
        self.status_combo.addItems(STATUS_OPTIONS)

        self.disposition_combo = QComboBox()
        self.disposition_combo.addItem("")
        self.disposition_combo.addItems(DISPOSITION_OPTIONS)

        self.responsibility_combo = QComboBox()
        self.responsibility_combo.addItems(RESPONSIBILITY_OPTIONS)

        apply_form_inputs(
            [
                self.event_date_edit,
                self.return_slip_type_combo,
                self.work_order_input,
                self.internal_work_order_input,
                self.transfer_slip_input,
                self.category_combo,
                self.item_no_input,
                self.product_name_input,
                self.qty_spin,
                self.supplier_combo,
                self.outsource_supplier_combo,
                self.status_combo,
                self.disposition_combo,
                self.responsibility_combo,
            ]
        )

        layout.setContentsMargins(*DEFECT_FORM_CONTENT_MARGINS)
        layout.setSpacing(SECTION_SPACING)

        # 1. 基礎資訊（2 欄佈局：避免最小寬度 / 高 DPI 下第三欄較寬的 combo 切字）
        form_grid = create_form_grid(field_count=2, horizontal_spacing=FORM_TWO_COLUMN_SPACING)

        # Row 0
        self._add_compact_field(form_grid, 0, LABEL_EVENT_DATE, self.event_date_edit, column_offset=0)
        self._add_compact_field(
            form_grid, 0, LABEL_RETURN_SLIP_TYPE, self.return_slip_type_combo,
            column_offset=2, required=True,
        )

        # Row 1
        self._add_compact_field(form_grid, 1, LABEL_CATEGORY, self.category_combo, column_offset=0)
        add_labeled_field(
            form_grid, 1, LABEL_QTY, self.qty_spin,
            column_offset=2,
            label_width_override=FORM_COMPACT_LABEL_WIDTH,
            field_minimum_width=FORM_COMPACT_FIELD_MIN_WIDTH,
            required=True,
        )

        # Row 2
        self._add_compact_field(
            form_grid, 2, LABEL_WORK_ORDER_NO, self.work_order_input, column_offset=0
        )
        self._add_compact_field(
            form_grid, 2, LABEL_INTERNAL_WORK_ORDER_NO, self.internal_work_order_input, column_offset=2
        )

        # Row 3
        self._add_compact_field(form_grid, 3, LABEL_ITEM_NO, self.item_no_input, column_offset=0, required=True)
        self.product_name_input.setToolTip("由系統依料號自動帶出，不可手動輸入")
        product_name_host = QWidget()
        product_name_layout = QHBoxLayout(product_name_host)
        product_name_layout.setContentsMargins(0, 0, 0, 0)
        product_name_layout.setSpacing(8)
        product_name_layout.addWidget(self.product_name_input, 1)
        product_name_layout.addWidget(self.quick_add_product_btn, 0)
        product_name_host.setMinimumWidth(FORM_COMPACT_FIELD_MIN_WIDTH + 84)
        add_labeled_field(
            form_grid, 3, LABEL_PRODUCT_NAME, product_name_host,
            column_offset=2,
            label_width_override=FORM_COMPACT_LABEL_WIDTH,
            field_minimum_width=FORM_COMPACT_FIELD_MIN_WIDTH,
        )

        # Row 4
        self._add_compact_field(
            form_grid, 4, LABEL_SUPPLIER_NAME, self.supplier_combo, column_offset=0
        )
        self._add_compact_field(
            form_grid, 4, LABEL_OUTSOURCE_SUPPLIER_NAME, self.outsource_supplier_combo, column_offset=2
        )
        layout.addLayout(form_grid)

        self.supplier_hint_label = make_notice_label("", role="warningHint")
        layout.addWidget(self.supplier_hint_label)

        # 分隔線或間距也可以在此加
        layout.addSpacing(10)

        # 2. 不良現象紀錄
        layout.addWidget(
            create_section_title_with_icon(
                LABEL_DEFECT_DESC, "section_description", required=True
            )
        )

        layout.addWidget(self.defect_desc_input)

        layout.addSpacing(10)

        # 3. 處理狀態（2 欄佈局）
        handle_grid = create_form_grid(field_count=2, horizontal_spacing=FORM_TWO_COLUMN_SPACING)
        self._add_compact_field(handle_grid, 0, LABEL_STATUS, self.status_combo, column_offset=0)
        self._add_compact_field(
            handle_grid, 0, LABEL_DISPOSITION, self.disposition_combo, column_offset=2
        )
        self._add_compact_field(
            handle_grid, 1, LABEL_TRANSFER_SLIP_NO, self.transfer_slip_input, column_offset=0
        )
        self._add_compact_field(
            handle_grid, 1, LABEL_RESPONSIBILITY, self.responsibility_combo, column_offset=2
        )
        layout.addLayout(handle_grid)

        layout.addStretch(1)

        self._setup_tab_order()

    def _setup_tab_order(self) -> None:
        """Tab follows visual reading order, not widget creation order (a11y §5).

        Several inputs (e.g. transfer_slip_input) are created earlier than they
        are placed, so without this the focus chain would jump around.
        """
        order = [
            self.event_date_edit,
            self.return_slip_type_combo,
            self.category_combo,
            self.qty_spin,
            self.work_order_input,
            self.internal_work_order_input,
            self.item_no_input,
            self.product_name_input,
            self.quick_add_product_btn,
            self.supplier_combo,
            self.outsource_supplier_combo,
            self.defect_desc_input,
            self.status_combo,
            self.disposition_combo,
            self.transfer_slip_input,
            self.responsibility_combo,
        ]
        for earlier, later in zip(order, order[1:]):
            self.setTabOrder(earlier, later)

    def _add_compact_field(
        self,
        layout,
        row: int,
        label_text: str,
        field: QWidget,
        *,
        column_offset: int = 0,
        required: bool = False,
    ) -> QLabel:
        return add_labeled_field(
            layout,
            row,
            label_text,
            field,
            column_offset=column_offset,
            label_width_override=FORM_COMPACT_LABEL_WIDTH,
            field_minimum_width=FORM_COMPACT_FIELD_MIN_WIDTH,
            required=required,
        )

    def _set_defect_desc_height(self) -> None:
        line_height = self.defect_desc_input.fontMetrics().lineSpacing()
        text_height = line_height * 4
        vertical_padding = 16
        document_margin = int(self.defect_desc_input.document().documentMargin() * 2)
        frame_height = self.defect_desc_input.frameWidth() * 2
        self.defect_desc_input.setFixedHeight(
            text_height + vertical_padding + document_margin + frame_height
        )

    def refresh_supplier_options(self, selected_text: str | None = None) -> None:
        current_supplier_text = (
            selected_text.strip()
            if selected_text is not None
            else self.supplier_combo.currentText().strip()
        )
        current_outsource_text = self.outsource_supplier_combo.currentText().strip()

        supplier_options = ["", "N/A"]
        supplier_options.extend(
            load_supplier_names_by_category(self.conn, SUPPLIER_CATEGORY_FORMAL)
        )

        outsource_options = ["", "N/A"]
        outsource_options.extend(
            load_supplier_names_by_category(self.conn, SUPPLIER_CATEGORY_OUTSOURCE)
        )

        self.supplier_combo.blockSignals(True)
        self.supplier_combo.clear()
        self.supplier_combo.addItems(supplier_options)
        if current_supplier_text and current_supplier_text not in supplier_options:
            self.supplier_combo.addItem(current_supplier_text)
        self.supplier_combo.setCurrentText(current_supplier_text)
        self.supplier_combo.blockSignals(False)

        self.outsource_supplier_combo.blockSignals(True)
        self.outsource_supplier_combo.clear()
        self.outsource_supplier_combo.addItems(outsource_options)
        if current_outsource_text and current_outsource_text not in outsource_options:
            self.outsource_supplier_combo.addItem(current_outsource_text)
        target_outsource_index = self.outsource_supplier_combo.findText(current_outsource_text)
        if target_outsource_index >= 0:
            self.outsource_supplier_combo.setCurrentIndex(target_outsource_index)
        else:
            self.outsource_supplier_combo.setCurrentIndex(-1)
        self.outsource_supplier_combo.blockSignals(False)

        self._sync_supplier_outsource_guard()

    def refresh_product_options(self, selected_item_no: str | None = None) -> None:
        current_item_no = (
            selected_item_no.strip()
            if selected_item_no is not None
            else self.item_no_input.currentText().strip()
        )
        products = product_service.list_products(self.conn)
        self._product_name_by_item_no = {
            item["item_no"].strip(): item["product_name"].strip()
            for item in products
            if item["item_no"].strip()
        }

        self.item_no_input.blockSignals(True)
        self.item_no_input.clear()
        self.item_no_input.addItem("", "")
        for item_no, product_name in self._product_name_by_item_no.items():
            self.item_no_input.addItem(item_no, item_no)
            index = self.item_no_input.count() - 1
            if product_name:
                self.item_no_input.setItemData(
                    index,
                    f"{item_no} / {product_name}",
                    Qt.ItemDataRole.ToolTipRole,
                )
        if current_item_no and self.item_no_input.findText(current_item_no) < 0:
            self.item_no_input.addItem(current_item_no, current_item_no)
        self.item_no_input.setCurrentText(current_item_no)
        self.item_no_input.blockSignals(False)
        self.sync_product_name_from_item_no()

    def reset_fields(self) -> None:
        self.event_date_edit.setDate(QDate.currentDate())
        self.return_slip_type_combo.setCurrentIndex(0)
        self.work_order_input.clear()
        self.internal_work_order_input.clear()
        self.transfer_slip_input.clear()
        self.category_combo.setCurrentIndex(0)
        self.item_no_input.setCurrentText("")
        self.product_name_input.clear()
        self.quick_add_product_btn.hide()
        self.qty_spin.setValue(1)
        self.supplier_combo.setCurrentText("")
        self.outsource_supplier_combo.setCurrentIndex(-1)
        self.defect_desc_input.clear()
        self.status_combo.setCurrentText(STATUS_OPTIONS[0])
        self.disposition_combo.setCurrentIndex(0)
        self.responsibility_combo.setCurrentIndex(0)
        self._sync_supplier_outsource_guard()

    def prepare_next_continuous_entry(self) -> None:
        self.transfer_slip_input.clear()
        self.item_no_input.setCurrentText("")
        self.product_name_input.clear()
        self.quick_add_product_btn.hide()
        self.qty_spin.setValue(1)
        self.defect_desc_input.clear()
        self.status_combo.setCurrentText(STATUS_OPTIONS[0])
        self.disposition_combo.setCurrentIndex(0)
        self.responsibility_combo.setCurrentIndex(0)
        self._sync_supplier_outsource_guard()

    def set_form_data(self, data) -> None:
        record = dict(data)
        event_date = QDate.fromString(record.get("event_date", ""), "yyyy-MM-dd")
        if event_date.isValid():
            self.event_date_edit.setDate(event_date)
        return_slip_type = str(record.get("return_slip_type", "") or "")
        if return_slip_type and self.return_slip_type_combo.findText(return_slip_type) == -1:
            self.return_slip_type_combo.addItem(return_slip_type)
        self.return_slip_type_combo.setCurrentText(return_slip_type)
        self.work_order_input.setText(record.get("work_order_no", ""))
        self.internal_work_order_input.setText(record.get("internal_work_order_no", ""))
        self.transfer_slip_input.setText(record.get("transfer_slip_no", ""))
        self.category_combo.setCurrentText(record.get("category", CATEGORY_OPTIONS[0]))
        self.refresh_product_options(str(record.get("item_no", "") or ""))
        self.sync_product_name_from_item_no()
        self.qty_spin.setValue(max(int(record.get("qty", 1)), 1))
        supplier_name = record.get("supplier_name", "")
        outsource_supplier_name = record.get("outsource_supplier_name", "")
        
        # If both are filled and neither is N/A, favor supplier (legacy cleanup)
        if (str(supplier_name).strip() and str(supplier_name).strip() != "N/A" and 
            str(outsource_supplier_name).strip() and str(outsource_supplier_name).strip() != "N/A"):
            outsource_supplier_name = "N/A"

        # refresh_supplier_options 內部會自行解除 blockSignals，無法依賴外層封鎖跨越此呼叫。
        # 它已在封鎖狀態下載入並設定供應商；之後僅需在「設定委外索引」這段重新封鎖，
        # 避免觸發互斥處理器把剛載入的供應商覆寫為 N/A，也避免載入即被標記為 dirty。
        self.refresh_supplier_options(supplier_name)
        self.outsource_supplier_combo.blockSignals(True)
        try:
            target_outsource_index = self.outsource_supplier_combo.findText(
                str(outsource_supplier_name)
            )
            self.outsource_supplier_combo.setCurrentIndex(target_outsource_index)
        finally:
            self.outsource_supplier_combo.blockSignals(False)
        self.defect_desc_input.setPlainText(record.get("defect_desc", ""))
        self.status_combo.setCurrentText(record.get("status", STATUS_OPTIONS[0]))
        disposition = record.get("disposition", "")
        if self.disposition_combo.findText(disposition) != -1:
            self.disposition_combo.setCurrentText(disposition)
        else:
            self.disposition_combo.setCurrentIndex(0)
        responsibility = record.get("responsibility", "")
        if self.responsibility_combo.findText(responsibility) == -1:
            self.responsibility_combo.addItem(responsibility)
        self.responsibility_combo.setCurrentText(responsibility)

        self._sync_supplier_outsource_guard()

    def get_form_data(self) -> dict[str, object]:
        return {
            "event_date": self.event_date_edit.date().toPython(),
            "return_slip_type": self.return_slip_type_combo.currentText(),
            "work_order_no": self.work_order_input.text(),
            "internal_work_order_no": self.internal_work_order_input.text(),
            "transfer_slip_no": self.transfer_slip_input.text(),
            "category": self.category_combo.currentText(),
            "item_no": self.item_no_input.currentText(),
            "product_name": self.product_name_input.text(),
            "qty": self.qty_spin.value(),
            "supplier_name": self.supplier_combo.currentText(),
            "outsource_supplier_name": self.outsource_supplier_combo.currentText(),
            "defect_desc": self.defect_desc_input.toPlainText(),
            "status": self.status_combo.currentText(),
            "disposition": self.disposition_combo.currentText(),
            "responsibility": self.responsibility_combo.currentText(),
        }

    def _on_supplier_changed(self, text: str) -> None:
        stripped = text.strip()
        if stripped and stripped != "N/A":
            self.outsource_supplier_combo.blockSignals(True)
            self.outsource_supplier_combo.setCurrentText("N/A")
            self.outsource_supplier_combo.blockSignals(False)
        elif not stripped or stripped == "N/A":
            if self.outsource_supplier_combo.currentText() == "N/A":
                self.outsource_supplier_combo.blockSignals(True)
                self.outsource_supplier_combo.setCurrentIndex(-1)
                self.outsource_supplier_combo.blockSignals(False)
        self._sync_supplier_outsource_guard()

    def _on_outsource_supplier_changed(self, text: str) -> None:
        stripped = text.strip()
        if stripped and stripped != "N/A":
            self.supplier_combo.blockSignals(True)
            self.supplier_combo.setCurrentText("N/A")
            self.supplier_combo.blockSignals(False)
        elif not stripped or stripped == "N/A":
            if self.supplier_combo.currentText() == "N/A":
                self.supplier_combo.blockSignals(True)
                self.supplier_combo.setCurrentText("")
                self.supplier_combo.blockSignals(False)
        self._sync_supplier_outsource_guard()

    def _sync_supplier_outsource_guard(self) -> None:
        def is_really_filled(combo: QComboBox) -> bool:
            t = combo.currentText().strip()
            return bool(t) and t != "N/A"

        apply_supplier_exclusion_lock(
            supplier_combo=self.supplier_combo,
            outsource_combo=self.outsource_supplier_combo,
            hint_label=self.supplier_hint_label,
            is_filled=is_really_filled,
        )

    def resolve_product_name_by_item_no(self, item_no: str) -> str:
        normalized_item_no = item_no.strip()
        if not normalized_item_no:
            return ""
        if normalized_item_no in self._product_name_by_item_no:
            return self._product_name_by_item_no[normalized_item_no]
        return product_service.get_product_name_by_item_no(self.conn, normalized_item_no) or ""

    def sync_product_name_from_item_no(self) -> str:
        product_name = self.resolve_product_name_by_item_no(self.item_no_input.currentText())
        self.product_name_input.setText(product_name)
        self._sync_quick_add_product_visibility(product_name)
        return product_name

    def has_known_product_item_no(self) -> bool:
        item_no = self.item_no_input.currentText().strip()
        if not item_no:
            return True
        return bool(self.sync_product_name_from_item_no())

    def _on_item_no_changed(self, _text: str) -> None:
        self.sync_product_name_from_item_no()

    def _sync_quick_add_product_visibility(self, product_name: str = "") -> None:
        item_no = self.item_no_input.currentText().strip()
        should_show = (
            self.allow_quick_product_create
            and bool(item_no)
            and not bool(product_name.strip())
        )
        self.quick_add_product_btn.setVisible(should_show)

    def open_quick_product_create_dialog(self) -> bool:
        item_no = self.item_no_input.currentText().strip()
        if not item_no:
            self._sync_quick_add_product_visibility("")
            return False
        dialog = QuickProductCreateDialog(self.conn, item_no, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._sync_quick_add_product_visibility(self.product_name_input.text())
            return False
        product_name = dialog.created_product_name or self.resolve_product_name_by_item_no(item_no)
        self.refresh_product_options(item_no)
        self.product_name_input.setText(product_name)
        self.quick_add_product_btn.hide()
        self.product_created.emit(item_no, product_name)
        return True

    def focus_item_no(self) -> None:
        self.item_no_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        line_edit = self.item_no_input.lineEdit()
        if line_edit is not None:
            line_edit.selectAll()


class DefectFormWidget(DirtyTrackingMixin, QWidget):
    saved = Signal()
    data_changed = Signal()
    status_message = Signal(str, int)

    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None):
        super().__init__(parent)
        self.conn = conn
        self.show_popups = True
        self._is_dirty = False
        self._track_changes = True
        self._is_saving = False
        self._build_ui()
        self._connect_dirty_tracking()
        self._mark_clean()

    def _build_ui(self) -> None:
        page, content_layout = create_page_shell(show_header=False)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(page)

        # Unified Card for Toolbar and Fields
        main_card, main_card_layout = create_section_card("")
        main_card_layout.setContentsMargins(22, 20, 22, 20)
        main_card_layout.setSpacing(12)

        # Toolbar Section
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(12)

        shortcut_label = make_hint_label(HINT_SAVE_SHORTCUT)
        toolbar.addWidget(shortcut_label)

        self.batch_mode_checkbox = QCheckBox(
            "連續登錄：儲存後保留日期/單別/類別/製令/供應商"
        )
        self.batch_mode_checkbox.setChecked(True)
        toolbar.addWidget(self.batch_mode_checkbox)
        toolbar.addStretch(1)

        self.reset_button = QPushButton("重置")
        self.clear_button = QPushButton("清除")
        self.save_button = QPushButton("儲存")
        self.reset_button.setToolTip("重置所有欄位為預設值")
        self.clear_button.setToolTip("清空所有輸入欄位內容")
        self.save_button.setToolTip("儲存目前表單內容（Ctrl+S）")
        set_button_role(self.reset_button, "reset")
        set_button_role(self.clear_button, "secondary")
        set_button_role(self.save_button, "primary")
        apply_button_icon(self.reset_button, "reset")
        apply_button_icon(self.clear_button, "clear")
        apply_button_icon(self.save_button, "save")
        self.save_button.clicked.connect(self.save_record)
        self.clear_button.clicked.connect(self.clear_form)
        self.reset_button.clicked.connect(self.reset_form)

        toolbar.addWidget(self.reset_button)
        toolbar.addWidget(self.clear_button)
        toolbar.addWidget(self.save_button)
        main_card_layout.addLayout(toolbar)

        self.feedback_label = make_notice_label("")
        main_card_layout.addWidget(self.feedback_label)

        # Divider
        line = QFrame()
        line.setProperty("uiRole", "divider")
        line.setFixedHeight(1)
        main_card_layout.addWidget(line)

        # Scrollable Fields Section
        self.fields_widget = DefectFieldsWidget(self.conn)
        self.fields_widget.product_created.connect(self._on_quick_product_created)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setWidget(self.fields_widget)
        
        main_card_layout.addWidget(scroll_area, 1)
        content_layout.addWidget(main_card, 1)

        self.save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        self.save_shortcut.activated.connect(self.save_record)

    def refresh_supplier_options(self) -> None:
        self.fields_widget.refresh_supplier_options()

    def refresh_product_options(self) -> None:
        self.fields_widget.refresh_product_options()

    def _on_quick_product_created(self, item_no: str, product_name: str) -> None:
        self._mark_dirty()
        self._show_feedback(
            f"已建立產品 {item_no} / {product_name}，可繼續完成不良品登錄。",
            role="successHint",
        )
        self.data_changed.emit()
        self.status_message.emit("快速產品已建立。", STATUS_TIMEOUT_SUCCESS)

    def focus_item_no(self) -> None:
        self.fields_widget.focus_item_no()

    def _connect_dirty_tracking(self) -> None:
        _connect_dirty_tracking_signals(self.fields_widget, self._mark_dirty)

    def has_unsaved_changes(self) -> bool:
        return self._is_dirty

    def _show_feedback(self, message: str, *, role: str = "notice", visible: bool = True) -> None:
        self.feedback_label.setProperty("uiRole", role)
        self.feedback_label.setText(message)
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)
        self.feedback_label.setVisible(visible and bool(message))

    def _confirm_discard_for_action(self, action_label: str) -> bool:
        if not self.has_unsaved_changes():
            return True
        result = QMessageBox.question(
            self,
            "未儲存變更",
            f"目前有未儲存資料，確定要{action_label}嗎？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            self.status_message.emit("未儲存變更已捨棄。", STATUS_TIMEOUT_SUCCESS)
            return True
        self.status_message.emit("已取消操作，請先處理未儲存資料。", STATUS_TIMEOUT_SUCCESS)
        return False

    def _set_save_busy_state(self, busy: bool) -> None:
        super()._set_save_busy_state(busy)
        self.save_button.setEnabled(not busy)
        self.clear_button.setEnabled(not busy)
        self.reset_button.setEnabled(not busy)
        self.save_shortcut.setEnabled(not busy)

    def _clear_form_internal(self) -> None:
        self._track_changes = False
        # 清除所有文字輸入，但保留數值與日期的預設值
        self.fields_widget.return_slip_type_combo.setCurrentIndex(0)
        self.fields_widget.item_no_input.setCurrentText("")
        self.fields_widget.work_order_input.clear()
        self.fields_widget.internal_work_order_input.clear()
        self.fields_widget.transfer_slip_input.clear()
        self.fields_widget.product_name_input.clear()
        self.fields_widget.supplier_combo.setCurrentText("")
        self.fields_widget.outsource_supplier_combo.setCurrentIndex(-1)
        self.fields_widget.defect_desc_input.clear()
        self.fields_widget.disposition_combo.setCurrentIndex(0)
        self.fields_widget._sync_supplier_outsource_guard()
        self._track_changes = True
        self._mark_clean()

    def _prepare_next_entry_after_save(self) -> None:
        self._track_changes = False
        if self.batch_mode_checkbox.isChecked():
            self.fields_widget.prepare_next_continuous_entry()
        else:
            self._clear_form_internal()
        self._track_changes = True
        self._mark_clean()

    def clear_form(self) -> None:
        if self._is_saving:
            return
        if not self._confirm_discard_for_action("清除欄位"):
            return
        self._clear_form_internal()
        self._show_feedback("已清除輸入欄位", visible=True)

    def reset_form(self) -> None:
        if self._is_saving:
            return
        if not self._confirm_discard_for_action("重置欄位"):
            return
        self._track_changes = False
        self.fields_widget.reset_fields()
        self.fields_widget.refresh_supplier_options()
        self._track_changes = True
        self._mark_clean()
        self._show_feedback("欄位已重置為初始狀態", visible=True)

    def _validate_item_no_product_mapping(self) -> bool:
        if self.fields_widget.has_known_product_item_no():
            return True
        message = VALIDATION_ITEM_NO_NOT_FOUND
        if self.show_popups:
            QMessageBox.warning(self, "欄位驗證", message)
        self._show_feedback(MSG_SAVE_FAILED.format(message), role="warningHint")
        self.status_message.emit(MSG_SAVE_FAILED.format(message), STATUS_TIMEOUT_ERROR)
        return False

    def save_record(self) -> bool:
        if self._is_saving:
            return False
        if not self._validate_item_no_product_mapping():
            return False
        self._set_save_busy_state(True)
        self._show_feedback(MSG_SAVING, role="notice")
        self.status_message.emit(MSG_SAVING, STATUS_TIMEOUT_PERSIST)
        try:
            defect_no = defect_service.create_defect(
                self.conn, self.fields_widget.get_form_data()
            )
        except ValueError as exc:
            if self.show_popups:
                QMessageBox.warning(self, "欄位驗證", str(exc))
            self._show_feedback(MSG_SAVE_FAILED.format(exc), role="warningHint")
            self.status_message.emit(MSG_SAVE_FAILED.format(exc), STATUS_TIMEOUT_ERROR)
            self._set_save_busy_state(False)
            return False
        except sqlite3.Error as exc:
            if self.show_popups:
                QMessageBox.critical(self, "資料庫錯誤", str(exc))
            self._show_feedback(MSG_SAVE_FAILED.format(exc), role="warningHint")
            self.status_message.emit(MSG_SAVE_FAILED.format(exc), STATUS_TIMEOUT_ERROR)
            self._set_save_busy_state(False)
            return False

        # Success feedback uses inline label + status bar; modal popup is redundant
        # (and prior behavior was triple-channel — see UX consistency audit C4).
        self._prepare_next_entry_after_save()
        self._show_feedback(MSG_SAVE_SUCCESS.format(defect_no), role="successHint")
        self.saved.emit()
        self.data_changed.emit()
        self.status_message.emit(MSG_SAVE_SUCCESS.format(defect_no), STATUS_TIMEOUT_SUCCESS)
        self._set_save_busy_state(False)
        return True

    def confirm_save_if_dirty(self) -> bool:
        if self._is_saving:
            return False
        if not self.has_unsaved_changes():
            return True

        result = QMessageBox.question(
            self,
            "未儲存變更",
            "目前有未儲存資料，是否先儲存？",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if result == QMessageBox.StandardButton.Cancel:
            self.status_message.emit("已取消切換，請先處理未儲存資料。", STATUS_TIMEOUT_SUCCESS)
            return False
        if result == QMessageBox.StandardButton.No:
            self._track_changes = False
            self.fields_widget.reset_fields()
            self.fields_widget.refresh_supplier_options()
            self._track_changes = True
            self._mark_clean()
            self._show_feedback("未儲存變更已捨棄。", role="warningHint")
            self.status_message.emit("未儲存變更已捨棄。", STATUS_TIMEOUT_SUCCESS)
            return True
        return self.save_record()


class DefectEditDialog(QDialog):
    def __init__(
        self,
        conn: sqlite3.Connection,
        defect_id: int,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.conn = conn
        self.defect_id = defect_id
        self._is_dirty = False
        self._track_changes = True
        self._is_saving = False
        self.setWindowTitle("編輯不良品資料")
        fit_window_to_available_screen(self, 1180, 760, enable_size_grip=True)
        self._build_ui()
        self._connect_dirty_tracking()
        self.load_record()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Unified Main Card for Dialog
        main_card, main_card_layout = create_section_card("")
        main_card_layout.setContentsMargins(18, 16, 18, 16)
        main_card_layout.setSpacing(10)

        # Record context
        self.info_label = QLabel()
        self.info_label.setProperty("uiRole", "pageSubtitle")
        self.info_label.setWordWrap(True)

        main_card_layout.addWidget(self.info_label)

        # Fields Section
        self.fields_widget = DefectFieldsWidget(
            self.conn,
            allow_quick_product_create=False,
        )
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setWidget(self.fields_widget)
        
        main_card_layout.addWidget(scroll_area, 1)

        # Bottom Buttons (Inside card)
        line2 = QFrame()
        line2.setProperty("uiRole", "divider")
        line2.setFixedHeight(1)
        main_card_layout.addWidget(line2)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 8, 0, 0)
        button_layout.setSpacing(12)
        
        self.save_button = QPushButton("儲存變更")
        self.cancel_button = QPushButton("取消")
        self.save_button.setMinimumWidth(DIALOG_ACTION_BUTTON_MIN_WIDTH)
        self.cancel_button.setMinimumWidth(DIALOG_ACTION_BUTTON_MIN_WIDTH)
        set_button_role(self.save_button, "primary")
        set_button_role(self.cancel_button, "secondary")
        apply_button_icon(self.save_button, "edit_save")
        apply_button_icon(self.cancel_button, "cancel")

        self.save_button.clicked.connect(self.save_changes)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addStretch(1)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        main_card_layout.addLayout(button_layout)

        layout.addWidget(main_card, 1)

    def _connect_dirty_tracking(self) -> None:
        _connect_dirty_tracking_signals(self.fields_widget, self._mark_dirty)

    def _mark_dirty(self, *_args: object) -> None:
        if self._track_changes:
            self._is_dirty = True

    def _mark_clean(self) -> None:
        self._is_dirty = False

    def _set_save_busy_state(self, busy: bool) -> None:
        self._is_saving = busy
        self.save_button.setEnabled(not busy)
        self.cancel_button.setEnabled(not busy)

    def _confirm_close_if_dirty(self) -> bool:
        if self._is_saving:
            return False
        if not self._is_dirty:
            return True
        result = QMessageBox.question(
            self,
            "未儲存變更",
            "目前有未儲存資料，是否先儲存？",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if result == QMessageBox.StandardButton.Cancel:
            return False
        if result == QMessageBox.StandardButton.No:
            return True
        return self.save_changes()

    def load_record(self) -> None:
        row = crud.get_defect_by_id(self.conn, self.defect_id)
        if row is None:
            raise ValueError(f"找不到資料 ID: {self.defect_id}")

        self.record = dict(row)
        self.info_label.setText(
            f"{LABEL_DEFECT_NO}：{self.record['defect_no']}    {HEADER_CREATED_AT}：{format_datetime(self.record['created_at'])}"
        )
        self._track_changes = False
        self.fields_widget.set_form_data(self.record)
        self._track_changes = True
        self._mark_clean()

    def save_changes(self) -> bool:
        if self._is_saving:
            return False
        if not self.fields_widget.has_known_product_item_no():
            QMessageBox.warning(self, "欄位驗證", VALIDATION_ITEM_NO_NOT_FOUND)
            return False
        self._set_save_busy_state(True)
        try:
            defect_service.update_defect(
                self.conn,
                self.defect_id,
                self.fields_widget.get_form_data(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "欄位驗證", str(exc))
            self._set_save_busy_state(False)
            return False
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "資料庫錯誤", str(exc))
            self._set_save_busy_state(False)
            return False

        self._mark_clean()
        self._set_save_busy_state(False)
        QMessageBox.information(self, "更新成功", MSG_UPDATE_SUCCESS)
        self.accept()
        return True

    def reject(self) -> None:
        if not self._confirm_close_if_dirty():
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self._confirm_close_if_dirty():
            event.ignore()
            return
        event.accept()
