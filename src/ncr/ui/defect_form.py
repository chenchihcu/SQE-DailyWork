from __future__ import annotations

import sqlite3
from collections.abc import Callable

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    NCR_DATE_FIELD_MIN_WIDTH,
    NCR_DEFECT_FORM_CONTENT_MARGINS,
    NCR_EDIT_DIALOG_CARD_MARGINS,
    NCR_FIELD_SPACING_Y,
    NCR_FORM_COMPACT_FIELD_MIN_WIDTH,
    NCR_FORM_TWO_COLUMN_SPACING,
    NCR_INPUT_HEIGHT,
    NCR_QUICK_ADD_BUTTON_MIN_WIDTH,
    NCR_SECTION_SPACING,
)
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
    block_signals,
    load_supplier_names_by_category,
)
from ncr.models.defect import (
    CATEGORY_OPTIONS,
    DISPOSITION_OPTIONS,
    PROCESSING_LINE_OPTIONS,
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
    LABEL_PROCESSING_LINE,
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
    VALIDATION_REQUIRED,
    PLACEHOLDER_DEFECT_DESC,
    PLACEHOLDER_OUTSOURCE_SUPPLIER,
    HEADER_CREATED_AT,
)
from ncr.services import defect_service, product_service
from services import event_service
from ncr.ui.ui_style import (
    DIALOG_ACTION_BUTTON_MIN_WIDTH,
    FORM_COMPACT_LABEL_WIDTH,
    STATUS_TIMEOUT_ERROR,
    STATUS_TIMEOUT_PERSIST,
    STATUS_TIMEOUT_SUCCESS,
    add_labeled_field,
    apply_form_inputs,
    create_form_grid,
    create_section_card,
    create_section_title,
    fit_window_to_available_screen,
    make_hint_label,
    make_notice_label,
    set_button_role,
    format_datetime,
)
from ui.widgets.common_widgets import RequiredFieldLabel
from ui.widgets.bullet_list_widget import BulletListWidget
from ui.widgets.product_form_dialog import ProductFormDialog


def _connect_dirty_tracking_signals(
    fields: "DefectFieldsWidget", on_dirty: Callable[..., None]
) -> None:
    fields.event_date_edit.dateChanged.connect(on_dirty)
    fields.processing_line_combo.currentTextChanged.connect(on_dirty)
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


def _run_defect_save(operation):
    """Run a defect service call, mapping the two expected failure types to a
    (severity, title, exception) triple so save_record / save_changes share
    one exception-classification table instead of copy-pasted except blocks
    (audit finding D13). Returns (result, None) on success, (None, error) on
    failure; each caller keeps its own feedback channel (inline label +
    status bar vs. plain QMessageBox)."""
    try:
        return operation(), None
    except ValueError as exc:
        return None, ("warning", "欄位驗證", exc)
    except sqlite3.Error as exc:
        return None, ("critical", "資料庫錯誤", exc)


class DirtyTrackingMixin:
    def _mark_dirty(self, *_args: object) -> None:
        if self._track_changes:
            self._is_dirty = True

    def _mark_clean(self) -> None:
        self._is_dirty = False

    def _set_save_busy_state(self, busy: bool) -> None:
        self._is_saving = busy


class DefectFieldsWidget(QWidget):
    product_created = Signal(str, str)

    def __init__(
        self,
        conn: sqlite3.Connection,
        parent: QWidget | None = None,
        *,
        allow_quick_product_create: bool = True,
        lazy_load: bool = False,
    ):
        super().__init__(parent)
        self.conn = conn
        self.allow_quick_product_create = allow_quick_product_create
        self._product_name_by_item_no: dict[str, str] = {}
        self._build_ui()
        self.reset_fields()
        # 初始化順序：先載入供應商清單，再載入料號（料號依供應商篩選）
        if not lazy_load:
            self.refresh_supplier_options()
            self.refresh_product_options()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(NCR_SECTION_SPACING)

        self.event_date_edit = QDateEdit()
        self.event_date_edit.setCalendarPopup(True)
        self.event_date_edit.setDisplayFormat("yyyy-MM-dd")
        # 確保 yyyy-MM-dd 與日曆鈕在 1.5x DPI 不被裁成 yyyy-MM
        self.event_date_edit.setMinimumWidth(NCR_DATE_FIELD_MIN_WIDTH)

        self.return_slip_type_combo = QComboBox()
        self.return_slip_type_combo.addItem("")
        self.return_slip_type_combo.addItems(RETURN_SLIP_TYPE_OPTIONS)
        self.return_slip_type_combo.setAccessibleName("銷退單種類")

        self.processing_line_combo = QComboBox()
        self.processing_line_combo.addItem("")
        self.processing_line_combo.addItems(PROCESSING_LINE_OPTIONS)
        self.processing_line_combo.setAccessibleName("處理線別")

        self.work_order_input = QLineEdit()
        self.work_order_input.setPlaceholderText("輸入工單號碼")
        self.work_order_input.setAccessibleName("工單號碼")
        self.internal_work_order_input = QLineEdit()
        self.internal_work_order_input.setPlaceholderText("輸入內部工單")
        self.internal_work_order_input.setAccessibleName("內部工單")
        self.transfer_slip_input = QLineEdit()
        self.transfer_slip_input.setPlaceholderText("輸入調撥單號")
        self.transfer_slip_input.setAccessibleName("調撥單號")
        self.category_combo = QComboBox()
        self.category_combo.addItems(CATEGORY_OPTIONS)
        self.category_combo.setAccessibleName("異常類別")

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
        self.product_name_input.setAccessibleName("產品名稱")
        self.quick_add_product_btn = QPushButton("+ 建立")
        self.quick_add_product_btn.setObjectName("quickAddProductButton")
        self.quick_add_product_btn.setText("建立產品主檔…")
        self.quick_add_product_btn.setToolTip("使用共用產品主檔表單建立目前料號")
        self.quick_add_product_btn.setAccessibleName("建立產品主檔")
        self.quick_add_product_btn.setCursor(Qt.PointingHandCursor)
        self.quick_add_product_btn.setVisible(False)
        self.quick_add_product_btn.setMinimumWidth(NCR_QUICK_ADD_BUTTON_MIN_WIDTH)
        set_button_role(self.quick_add_product_btn, "secondary")
        self.quick_add_product_btn.clicked.connect(self.open_product_master_dialog)

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 1_000_000)
        self.qty_spin.setMinimumHeight(NCR_INPUT_HEIGHT)
        self.qty_spin.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)

        self.supplier_combo = QComboBox()
        self.supplier_combo.setEditable(True)
        self.supplier_combo.setAccessibleName("供應商名稱")

        self.outsource_supplier_combo = QComboBox()
        self.outsource_supplier_combo.setEditable(False)
        self.outsource_supplier_combo.setPlaceholderText(PLACEHOLDER_OUTSOURCE_SUPPLIER)
        self.outsource_supplier_combo.setAccessibleName("委外加工廠名稱")
        self.supplier_combo.currentTextChanged.connect(self._on_supplier_changed)
        self.supplier_combo.currentTextChanged.connect(
            self._on_supplier_changed_refresh_products
        )
        self.outsource_supplier_combo.currentTextChanged.connect(
            self._on_outsource_supplier_changed
        )
        self.outsource_supplier_combo.currentTextChanged.connect(
            self._on_supplier_changed_refresh_products
        )
        self.item_no_input.currentTextChanged.connect(self._on_item_no_changed)

        self.defect_desc_input = BulletListWidget(placeholder=PLACEHOLDER_DEFECT_DESC)
        self.defect_desc_input.setAccessibleName("不良描述")

        self.status_combo = QComboBox()
        self.status_combo.addItems(STATUS_OPTIONS)
        self.status_combo.setAccessibleName("處理狀態")

        self.disposition_combo = QComboBox()
        self.disposition_combo.addItem("")
        self.disposition_combo.addItems(DISPOSITION_OPTIONS)
        self.disposition_combo.setAccessibleName("處置方式")

        self._apply_default_disposition()
        try:
            from services.appearance_preferences_service import load_application_preferences
            prefs = load_application_preferences()
            if prefs.auto_uppercase_part_no:
                for line_edit in (self.work_order_input, self.internal_work_order_input, self.transfer_slip_input, self.item_no_input):
                    line_edit.textChanged.connect(lambda t, w=line_edit: w.setText(t.upper()) if t != t.upper() else None)
        except Exception:
            pass

        self.responsibility_combo = QComboBox()
        self.responsibility_combo.addItems(RESPONSIBILITY_OPTIONS)
        self.responsibility_combo.setAccessibleName("責任歸屬")

        apply_form_inputs(
            [
                self.event_date_edit,
                self.processing_line_combo,
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


        layout.setContentsMargins(*NCR_DEFECT_FORM_CONTENT_MARGINS)
        layout.setSpacing(NCR_SECTION_SPACING)

        # 1. 基礎資訊（2 欄標準對稱佈局：各列左右欄位水平精確對齊）
        layout.addWidget(create_section_title("📋 基礎資訊"))
        form_grid = create_form_grid(field_count=2, horizontal_spacing=NCR_FORM_TWO_COLUMN_SPACING)

        item_no_container = QWidget()
        item_no_layout = QHBoxLayout(item_no_container)
        item_no_layout.setContentsMargins(0, 0, 0, 0)
        item_no_layout.setSpacing(6)
        item_no_layout.addWidget(self.item_no_input, 1)
        item_no_layout.addWidget(self.quick_add_product_btn)

        # Row 0: 發生日期 / 責任
        self._add_compact_field(
            form_grid, 0, LABEL_EVENT_DATE, self.event_date_edit,
            column_offset=0
        )
        self._add_compact_field(
            form_grid, 0, LABEL_RESPONSIBILITY, self.responsibility_combo,
            column_offset=2
        )

        # Row 1: 類別 / 處理線
        self._add_compact_field(
            form_grid, 1, LABEL_CATEGORY, self.category_combo,
            column_offset=0
        )
        self._add_compact_field(
            form_grid, 1, LABEL_PROCESSING_LINE, self.processing_line_combo,
            column_offset=2, required=True
        )

        # Row 2: 正式供應商 / 委外供應商
        self._add_compact_field(
            form_grid, 2, LABEL_SUPPLIER_NAME, self.supplier_combo,
            column_offset=0
        )
        self._add_compact_field(
            form_grid, 2, LABEL_OUTSOURCE_SUPPLIER_NAME, self.outsource_supplier_combo,
            column_offset=2
        )

        # Row 3: 退料單別 / 數量
        self._add_compact_field(
            form_grid, 3, LABEL_RETURN_SLIP_TYPE, self.return_slip_type_combo,
            column_offset=0, required=True
        )
        self._add_compact_field(
            form_grid, 3, LABEL_QTY, self.qty_spin,
            column_offset=2, required=True
        )

        # Row 4: 料號 / 產品名稱
        self._add_compact_field(
            form_grid, 4, LABEL_ITEM_NO, item_no_container,
            column_offset=0, required=True
        )
        self._add_compact_field(
            form_grid, 4, LABEL_PRODUCT_NAME, self.product_name_input,
            column_offset=2
        )

        # Row 5: 廠內製令 / 委外製令
        self._add_compact_field(
            form_grid, 5, LABEL_INTERNAL_WORK_ORDER_NO, self.internal_work_order_input,
            column_offset=0
        )
        self._add_compact_field(
            form_grid, 5, LABEL_WORK_ORDER_NO, self.work_order_input,
            column_offset=2
        )

        layout.addLayout(form_grid)

        self.supplier_hint_label = make_notice_label("", role="messageText")
        layout.addWidget(self.supplier_hint_label)

        layout.addSpacing(10)

        # 2. 不良現象紀錄
        layout.addWidget(create_section_title(f"🔍 {LABEL_DEFECT_DESC}", required=True))

        layout.addWidget(self.defect_desc_input)

        layout.addSpacing(10)

        # 3. 處理狀態（3 欄單列佈局）
        layout.addWidget(create_section_title("⚙️ 處理狀態"))
        handle_grid = create_form_grid(field_count=3, horizontal_spacing=NCR_FORM_TWO_COLUMN_SPACING)
        self._add_compact_field(
            handle_grid, 0, LABEL_DISPOSITION, self.disposition_combo,
            column_offset=0, field_column_span=1
        )
        self._add_compact_field(
            handle_grid, 0, LABEL_TRANSFER_SLIP_NO, self.transfer_slip_input,
            column_offset=2, field_column_span=1
        )
        self._add_compact_field(
            handle_grid, 0, LABEL_STATUS, self.status_combo,
            column_offset=4, field_column_span=1
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
            self.responsibility_combo,
            self.category_combo,
            self.processing_line_combo,
            self.supplier_combo,
            self.outsource_supplier_combo,
            self.return_slip_type_combo,
            self.qty_spin,
            self.item_no_input,
            self.quick_add_product_btn,
            self.product_name_input,
            self.internal_work_order_input,
            self.work_order_input,
            self.defect_desc_input,
            self.disposition_combo,
            self.transfer_slip_input,
            self.status_combo,
        ]
        for earlier, later in zip(order, order[1:], strict=False):
            self.setTabOrder(earlier, later)

    def _add_compact_field(
        self,
        layout,
        row: int,
        label_text: str,
        field: QWidget,
        *,
        column_offset: int = 0,
        field_column_span: int = 1,
        required: bool = False,
    ) -> QLabel:
        # Use RequiredFieldLabel for required fields to match main-app pattern
        # (ui-ux-universal §2: unified red asterisk markers)
        if required:
            from ncr.ui.ui_style import apply_input_style
            label = RequiredFieldLabel(label_text)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            label.setFixedWidth(FORM_COMPACT_LABEL_WIDTH)
            apply_input_style(widget=field, minimum_width=NCR_FORM_COMPACT_FIELD_MIN_WIDTH)
            layout.addWidget(label, row, column_offset)
            layout.addWidget(field, row, column_offset + 1, 1, field_column_span)
            return label
        return add_labeled_field(
            layout,
            row,
            label_text,
            field,
            column_offset=column_offset,
            field_column_span=field_column_span,
            label_width_override=FORM_COMPACT_LABEL_WIDTH,
            field_minimum_width=NCR_FORM_COMPACT_FIELD_MIN_WIDTH,
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

        with block_signals(self.supplier_combo):
            self.supplier_combo.clear()
            self.supplier_combo.addItems(supplier_options)
            if current_supplier_text and current_supplier_text not in supplier_options:
                self.supplier_combo.addItem(current_supplier_text)
            self.supplier_combo.setCurrentText(current_supplier_text)

        with block_signals(self.outsource_supplier_combo):
            self.outsource_supplier_combo.clear()
            self.outsource_supplier_combo.addItems(outsource_options)
            if current_outsource_text and current_outsource_text not in outsource_options:
                self.outsource_supplier_combo.addItem(current_outsource_text)
            target_outsource_index = self.outsource_supplier_combo.findText(current_outsource_text)
            if target_outsource_index >= 0:
                self.outsource_supplier_combo.setCurrentIndex(target_outsource_index)
            else:
                self.outsource_supplier_combo.setCurrentIndex(-1)

        self._sync_supplier_outsource_guard()

    def _get_current_supplier_name(self) -> str:
        """取當前有效的供應商名稱（正式或委外，互斥，至多一個有效）。

        N/A 與空字串均視為無效，傳回空字串表示供應商未選定。
        """
        supplier_text = self.supplier_combo.currentText().strip()
        if supplier_text and supplier_text != "N/A":
            return supplier_text
        outsource_text = self.outsource_supplier_combo.currentText().strip()
        if outsource_text and outsource_text != "N/A":
            return outsource_text
        return ""

    def refresh_product_options(self, selected_item_no: str | None = None) -> None:
        """依當前選定的供應商重建料號下拉清單。

        若有供應商選定，嚴格篩選只顯示該供應商（主供/次供）的料號。
        若供應商未選定，料號清單為空（只有佔位選項）。
        若 selected_item_no 傳入，嘗試在重建後預選該值；
        但若該值不在篩選結果中，則不強制注入（新增模式下的嚴格行為）。
        """
        current_item_no = (
            selected_item_no.strip()
            if selected_item_no is not None
            else self._current_item_no()
        )
        supplier_name = self._get_current_supplier_name()
        if supplier_name:
            products = product_service.list_products_by_supplier_name(
                self.conn, supplier_name
            )
        else:
            products = []
        self._product_name_by_item_no = {
            (item["item_no"] or "").strip(): (item["product_name"] or "").strip()
            for item in products
            if (item["item_no"] or "").strip()
        }

        with block_signals(self.item_no_input):
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
            # 舊資料載入（編輯模式）：若目前料號不在篩選結果中，仍注入以保持可見
            if current_item_no and self.item_no_input.findText(current_item_no) < 0:
                self.item_no_input.addItem(current_item_no, current_item_no)
            self.item_no_input.setCurrentText(current_item_no)
        self.sync_product_name_from_item_no()

    def _on_supplier_changed_refresh_products(self, _text: str) -> None:
        """供應商改變時：清空料號與品名，依新供應商重建料號清單。

        此方法在 supplier_combo 與 outsource_supplier_combo 的
        currentTextChanged signal 觸發，但需等互斥邏輯（_on_supplier_changed /
        _on_outsource_supplier_changed）執行完後才讀取最終狀態，
        故以 currentText 實際值為準，不依賴傳入的 _text。
        """
        with block_signals(self.item_no_input):
            self.item_no_input.setCurrentText("")
        self.product_name_input.clear()
        self.quick_add_product_btn.hide()
        self.refresh_product_options("")

    _ALL_FIELD_GROUPS = frozenset({
        "date", "processing_line", "return_slip_type", "work_order", "transfer_slip",
        "category", "product", "qty", "supplier", "description",
        "status", "disposition", "responsibility",
    })

    def _apply_default_disposition(self) -> None:
        """套用使用者偏好的預設處置方式；未設定或清單中不存在時退回第一個選項。

        保留 try/except 防禦包覆與惰性 import：偏好服務為選用相依，
        不可因偏好讀取失敗阻斷表單建構或欄位重置。
        """
        try:
            from services.appearance_preferences_service import load_application_preferences
            prefs = load_application_preferences()
            if prefs.default_defect_disposition and self.disposition_combo.findText(prefs.default_defect_disposition) != -1:
                self.disposition_combo.setCurrentText(prefs.default_defect_disposition)
            else:
                self.disposition_combo.setCurrentIndex(0)
        except Exception:
            self.disposition_combo.setCurrentIndex(0)

    def _reset_field_group(self, groups: set[str]) -> None:
        """Reset a named subset of form fields. Shared by reset_fields (all
        groups), prepare_next_continuous_entry (a subset that preserves
        supplier/date/work_order for consecutive same-batch entry), and
        DefectFormWidget._clear_form_internal (all groups, to match its
        "清除" button tooltip's "清空所有輸入欄位內容" promise) -- so all
        three call sites share one authoritative field list instead of each
        maintaining its own drifting copy (audit findings A3/D4)."""
        if "date" in groups:
            self.event_date_edit.setDate(QDate.currentDate())
        if "processing_line" in groups:
            self.processing_line_combo.setCurrentIndex(0)
        if "return_slip_type" in groups:
            self.return_slip_type_combo.setCurrentIndex(0)
        if "work_order" in groups:
            self.work_order_input.clear()
            self.internal_work_order_input.clear()
        if "transfer_slip" in groups:
            self.transfer_slip_input.clear()
        if "category" in groups:
            self.category_combo.setCurrentIndex(0)
        if "product" in groups:
            self.item_no_input.setCurrentText("")
            self.product_name_input.clear()
            self.quick_add_product_btn.hide()
        if "qty" in groups:
            self.qty_spin.setValue(1)
        if "supplier" in groups:
            self.supplier_combo.setCurrentText("")
            self.outsource_supplier_combo.setCurrentIndex(-1)
        if "description" in groups:
            self.defect_desc_input.clear()
        if "status" in groups:
            self.status_combo.setCurrentText(STATUS_OPTIONS[0])
        if "disposition" in groups:
            self._apply_default_disposition()
        if "responsibility" in groups:
            self.responsibility_combo.setCurrentIndex(0)

        self._sync_supplier_outsource_guard()

    def reset_fields(self) -> None:
        self._reset_field_group(self._ALL_FIELD_GROUPS)

    def prepare_next_continuous_entry(self) -> None:
        self._reset_field_group({
            "transfer_slip", "product", "qty", "description",
            "status", "disposition", "responsibility",
        })

    def set_form_data(self, data) -> None:
        record = dict(data)
        event_date = QDate.fromString(record.get("event_date", ""), "yyyy-MM-dd")
        if event_date.isValid():
            self.event_date_edit.setDate(event_date)
        processing_line = str(record.get("processing_line", "") or "")
        if processing_line and self.processing_line_combo.findText(processing_line) == -1:
            self.processing_line_combo.addItem(processing_line)
        self.processing_line_combo.setCurrentText(processing_line)
        return_slip_type = str(record.get("return_slip_type", "") or "")
        if return_slip_type and self.return_slip_type_combo.findText(return_slip_type) == -1:
            self.return_slip_type_combo.addItem(return_slip_type)
        self.return_slip_type_combo.setCurrentText(return_slip_type)
        self.work_order_input.setText(str(record.get("work_order_no", "") or ""))
        self.internal_work_order_input.setText(str(record.get("internal_work_order_no", "") or ""))
        self.transfer_slip_input.setText(str(record.get("transfer_slip_no", "") or ""))
        self.category_combo.setCurrentText(record.get("category", CATEGORY_OPTIONS[0]))
        self.qty_spin.setValue(max(int(record.get("qty", 1)), 1))
        supplier_name = record.get("supplier_name", "")
        outsource_supplier_name = record.get("outsource_supplier_name", "")

        # If both are filled and neither is N/A, favor supplier (legacy cleanup)
        if (str(supplier_name).strip() and str(supplier_name).strip() != "N/A" and
                str(outsource_supplier_name).strip() and str(outsource_supplier_name).strip() != "N/A"):
            outsource_supplier_name = "N/A"

        # 就設定順序：先載入供應商 → 再載入料號（料號依供應商篩選）
        # refresh_supplier_options 內部會自行解除 blockSignals，無法依賴外層封鎖跨越此呼叫。
        # 它已在封鎖狀態下載入並設定供應商；之後僅需在「設定委外索引」這段重新封鎖，
        # 避免觸發互斥處理器把剛載入的供應商覆寫為 N/A。
        self.refresh_supplier_options(supplier_name)
        self.outsource_supplier_combo.blockSignals(True)
        try:
            target_outsource_index = self.outsource_supplier_combo.findText(
                str(outsource_supplier_name)
            )
            self.outsource_supplier_combo.setCurrentIndex(target_outsource_index)
        finally:
            self.outsource_supplier_combo.blockSignals(False)

        # 供應商已設定，再載入料號（篩選有效）
        self.refresh_product_options(str(record.get("item_no", "") or ""))
        self.sync_product_name_from_item_no()
        self.defect_desc_input.setPlainText(str(record.get("defect_desc", "") or ""))
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
            "processing_line": self.processing_line_combo.currentText(),
            "return_slip_type": self.return_slip_type_combo.currentText(),
            "work_order_no": self.work_order_input.text(),
            "internal_work_order_no": self.internal_work_order_input.text(),
            "transfer_slip_no": self.transfer_slip_input.text(),
            "category": self.category_combo.currentText(),
            "item_no": self._current_item_no(),
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
            with block_signals(self.outsource_supplier_combo):
                self.outsource_supplier_combo.setCurrentText("N/A")
        elif not stripped or stripped == "N/A":
            if self.outsource_supplier_combo.currentText() == "N/A":
                with block_signals(self.outsource_supplier_combo):
                    self.outsource_supplier_combo.setCurrentIndex(-1)
        self._sync_supplier_outsource_guard()

    def _on_outsource_supplier_changed(self, text: str) -> None:
        stripped = text.strip()
        if stripped and stripped != "N/A":
            with block_signals(self.supplier_combo):
                self.supplier_combo.setCurrentText("N/A")
        elif not stripped or stripped == "N/A":
            if self.supplier_combo.currentText() == "N/A":
                with block_signals(self.supplier_combo):
                    self.supplier_combo.setCurrentText("")
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

    def _current_item_no(self) -> str:
        line_edit = self.item_no_input.lineEdit()
        if line_edit is not None:
            text = line_edit.text().strip()
            if text:
                return text
        return self.item_no_input.currentText().strip()

    def resolve_product_name_by_item_no(self, item_no: str) -> str:
        normalized_item_no = item_no.strip()
        if not normalized_item_no:
            return ""
        if normalized_item_no in self._product_name_by_item_no:
            return self._product_name_by_item_no[normalized_item_no]
        return product_service.get_product_name_by_item_no(self.conn, normalized_item_no) or ""

    def sync_product_name_from_item_no(self) -> str:
        product_name = self.resolve_product_name_by_item_no(self._current_item_no())
        self.product_name_input.setText(product_name)
        self._sync_quick_add_product_visibility(product_name)
        return product_name

    def item_no_validation_error(self) -> str | None:
        """Return the blocking validation message for the item-no field, or
        None when valid. Blank is rejected here (audit finding A10): the
        field carries a required marker and the service layer already
        enforces it, so the UI pre-check must agree instead of deferring
        blank input to the later, generic ValueError path."""
        item_no = self._current_item_no()
        if not item_no:
            return VALIDATION_REQUIRED.format(LABEL_ITEM_NO)
        if not self.sync_product_name_from_item_no():
            return VALIDATION_ITEM_NO_NOT_FOUND
        return None

    def _on_item_no_changed(self, _text: str) -> None:
        self.sync_product_name_from_item_no()

    def _sync_quick_add_product_visibility(self, product_name: str = "") -> None:
        item_no = self._current_item_no()
        should_show = (
            self.allow_quick_product_create
            and bool(item_no)
            and not bool(product_name.strip())
        )
        self.quick_add_product_btn.setVisible(should_show)

    def open_product_master_dialog(self) -> bool:
        item_no = self._current_item_no()
        if not item_no:
            self._sync_quick_add_product_visibility("")
            return False
        suppliers = event_service.list_active_suppliers()
        if not suppliers:
            self._show_product_master_error("目前沒有可用供應商，請先到基礎資料建立供應商。")
            return False
        supplier_name = self.supplier_combo.currentText().strip()
        supplier_id = next(
            (
                str(row.get("id") or "").strip()
                for row in suppliers
                if str(row.get("supplier_name") or "").strip() == supplier_name
            ),
            "",
        )
        dialog = ProductFormDialog(
            suppliers,
            self,
            initial_data={
                "product_code": item_no,
                "supplier_id": supplier_id,
            },
            is_edit=False,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._sync_quick_add_product_visibility(self.product_name_input.text())
            return False
        payload = dialog.payload()
        try:
            event_service.create_product(payload)
        except (ValueError, sqlite3.Error) as exc:
            self._show_product_master_error(str(exc))
            return False
        product_name = str(payload.get("product_name") or "").strip()
        self.refresh_product_options(item_no)
        self.product_name_input.setText(product_name)
        self.quick_add_product_btn.hide()
        self.product_created.emit(item_no, product_name)
        return True

    def _show_product_master_error(self, message: str) -> None:
        self.supplier_hint_label.setText(message)
        self.supplier_hint_label.setVisible(True)
        self.product_name_input.setToolTip(message)
        self.product_name_input.setProperty("validationState", "error")
        self.product_name_input.style().unpolish(self.product_name_input)
        self.product_name_input.style().polish(self.product_name_input)

    def focus_item_no(self) -> None:
        self.item_no_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        line_edit = self.item_no_input.lineEdit()
        if line_edit is not None:
            line_edit.selectAll()


class DefectFormWidget(DirtyTrackingMixin, QWidget):
    saved = Signal()
    data_changed = Signal()
    status_message = Signal(str, int)

    def __init__(
        self,
        conn: sqlite3.Connection,
        parent: QWidget | None = None,
        *,
        lazy_load: bool = False,
    ):
        super().__init__(parent)
        self.conn = conn
        self.show_popups = True
        self._is_dirty = False
        self._track_changes = True
        self._is_saving = False
        self._build_ui(lazy_load=lazy_load)
        self._connect_dirty_tracking()
        self._mark_clean()

    def _build_ui(self, *, lazy_load: bool = False) -> None:
        from ui.widgets.common_widgets import CreateWorkflowShell

        self.workflow_shell = CreateWorkflowShell(self)
        self.workflow_shell.setObjectName("NcrCreateWorkflowShell")
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.workflow_shell)

        shortcut_label = make_hint_label(HINT_SAVE_SHORTCUT)
        self.workflow_shell.add_context(shortcut_label)

        self.batch_mode_checkbox = QCheckBox(
            "連續登錄：儲存後保留日期/單別/類別/製令/供應商"
        )
        self.batch_mode_checkbox.setChecked(True)
        self.workflow_shell.add_context(self.batch_mode_checkbox)

        self.reset_button = QPushButton("重置")
        self.clear_button = QPushButton("清除")
        self.save_button = QPushButton("儲存")
        self.reset_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.reset_button.setAccessibleName("重置表單")
        self.clear_button.setAccessibleName("清空表單")
        self.save_button.setAccessibleName("儲存表單")
        self.reset_button.setToolTip("重置所有欄位為預設值")
        self.clear_button.setToolTip("清空所有輸入欄位內容")
        self.save_button.setToolTip("儲存目前表單內容（Ctrl+S）")
        set_button_role(self.reset_button, "reset")
        set_button_role(self.clear_button, "secondary")
        set_button_role(self.save_button, "primary")
        self.save_button.clicked.connect(self.save_record)
        self.clear_button.clicked.connect(self.clear_form)
        self.reset_button.clicked.connect(self.reset_form)

        self.workflow_shell.add_context(self.reset_button)
        self.workflow_shell.add_context(self.clear_button)
        self.workflow_shell.add_action(self.save_button)

        self.feedback_label = self.workflow_shell.feedback_label

        self.fields_widget = DefectFieldsWidget(self.conn, lazy_load=lazy_load)
        self.fields_widget.product_created.connect(self._on_quick_product_created)
        self.workflow_shell.set_content(self.fields_widget)

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
            tone="success",
        )
        self.data_changed.emit()
        self.status_message.emit("快速產品已建立。", STATUS_TIMEOUT_SUCCESS)

    def focus_item_no(self) -> None:
        self.fields_widget.focus_item_no()

    def _connect_dirty_tracking(self) -> None:
        _connect_dirty_tracking_signals(self.fields_widget, self._mark_dirty)

    def has_unsaved_changes(self) -> bool:
        return self._is_dirty

    def _show_feedback(self, message: str, *, tone: str | None = None, visible: bool = True) -> None:
        if not visible:
            message = ""
        self.workflow_shell.show_feedback(message, tone=tone)

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
        # 清空所有欄位以符合「清除」按鈕 tooltip 承諾的行為（audit finding A3）。
        self.fields_widget._reset_field_group(DefectFieldsWidget._ALL_FIELD_GROUPS)
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
        message = self.fields_widget.item_no_validation_error()
        if message is None:
            return True
        if self.show_popups:
            QMessageBox.warning(self, "欄位驗證", message)
        self._show_feedback(MSG_SAVE_FAILED.format(message), tone="warning")
        self.status_message.emit(MSG_SAVE_FAILED.format(message), STATUS_TIMEOUT_ERROR)
        return False

    def save_record(self) -> bool:
        if self._is_saving:
            return False
        if not self._validate_item_no_product_mapping():
            return False
        self._set_save_busy_state(True)
        self._show_feedback(MSG_SAVING)
        self.status_message.emit(MSG_SAVING, STATUS_TIMEOUT_PERSIST)
        defect_no, save_error = _run_defect_save(
            lambda: defect_service.create_defect(
                self.conn, self.fields_widget.get_form_data()
            )
        )
        if save_error is not None:
            severity, title, exc = save_error
            if self.show_popups:
                show = QMessageBox.warning if severity == "warning" else QMessageBox.critical
                show(self, title, str(exc))
            self._show_feedback(MSG_SAVE_FAILED.format(exc), tone="warning")
            self.status_message.emit(MSG_SAVE_FAILED.format(exc), STATUS_TIMEOUT_ERROR)
            self._set_save_busy_state(False)
            return False

        # Success feedback uses inline label + status bar; modal popup is redundant
        # (and prior behavior was triple-channel — see UX consistency audit C4).
        self._prepare_next_entry_after_save()
        self._show_feedback(MSG_SAVE_SUCCESS.format(defect_no), tone="success")
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
            self._show_feedback("未儲存變更已捨棄。", tone="warning")
            self.status_message.emit("未儲存變更已捨棄。", STATUS_TIMEOUT_SUCCESS)
            return True
        return self.save_record()


class DefectEditDialog(DirtyTrackingMixin, QDialog):
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
        self.setModal(True)
        self.setWindowTitle("編輯不良品資料")
        fit_window_to_available_screen(self, 1180, 760, enable_size_grip=True)
        self._build_ui()
        self._connect_dirty_tracking()
        self.load_record()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        layout.setSpacing(12)

        # Unified Main Card for Dialog
        main_card, main_card_layout = create_section_card("")
        main_card_layout.setContentsMargins(*NCR_EDIT_DIALOG_CARD_MARGINS)
        main_card_layout.setSpacing(10)

        # Record context
        self.info_label = QLabel()
        self.info_label.setProperty("role", "helperText")
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
        line2.setProperty("role", "separator")
        line2.setFixedHeight(1)
        main_card_layout.addWidget(line2)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 8, 0, 0)
        button_layout.setSpacing(12)
        
        self.save_button = QPushButton("儲存變更")
        self.cancel_button = QPushButton("取消")
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.setAccessibleName("儲存變更")
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.setAccessibleName("取消變更")
        self.save_button.setMinimumWidth(DIALOG_ACTION_BUTTON_MIN_WIDTH)
        self.cancel_button.setMinimumWidth(DIALOG_ACTION_BUTTON_MIN_WIDTH)
        set_button_role(self.save_button, "primary")
        set_button_role(self.cancel_button, "secondary")

        self.convert_anomaly_button = QPushButton("轉開供應商異常")
        self.convert_anomaly_button.setAccessibleName("轉開供應商異常")
        self.convert_anomaly_button.setMinimumWidth(DIALOG_ACTION_BUTTON_MIN_WIDTH)
        set_button_role(self.convert_anomaly_button, "secondary")
        self.convert_anomaly_button.clicked.connect(self.convert_to_supplier_anomaly)

        self.save_button.clicked.connect(self.save_changes)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self.convert_anomaly_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        main_card_layout.addLayout(button_layout)

        layout.addWidget(main_card, 1)

    def convert_to_supplier_anomaly(self) -> None:
        row = crud.get_defect_by_id(self.conn, self.defect_id)
        if row is None:
            QMessageBox.warning(self, "無法轉開異常", "找不到目前的不合格品資料。")
            return
        data = dict(row)
        supplier_id = str(data.get("supplier_id") or "").strip()
        product_id = ""
        if supplier_id:
            product = self.conn.execute(
                """
                SELECT id, product_name, product_stage
                FROM products
                WHERE supplier_id = ? AND product_code = ?
                LIMIT 1
                """,
                (supplier_id, str(data.get("item_no") or "").strip()),
            ).fetchone()
            if product is not None:
                product_id = str(product["id"] or "")
                data["product_stage"] = product["product_stage"]
        main_window = self.window()
        if not hasattr(main_window, "open_new_anomaly_create_page"):
            QMessageBox.warning(self, "無法轉開異常", "目前視窗不支援供應商異常建立流程。")
            return
        main_window.open_new_anomaly_create_page(
            {
                "supplier_id": supplier_id,
                "supplier_name": (
                    data.get("outsource_supplier_name")
                    or data.get("supplier_name")
                    or ""
                ),
                "product_id": product_id,
                "product_name": data.get("product_name") or "",
                "problem_desc": data.get("defect_desc") or "",
                "anomaly_date": data.get("event_date") or "",
                "source_defect_no": data.get("defect_no") or "",
            }
        )
        self.accept()

    def _connect_dirty_tracking(self) -> None:
        _connect_dirty_tracking_signals(self.fields_widget, self._mark_dirty)

    def _set_save_busy_state(self, busy: bool) -> None:
        super()._set_save_busy_state(busy)
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
        item_no_error = self.fields_widget.item_no_validation_error()
        if item_no_error is not None:
            QMessageBox.warning(self, "欄位驗證", item_no_error)
            return False
        self._set_save_busy_state(True)
        _, save_error = _run_defect_save(
            lambda: defect_service.update_defect(
                self.conn,
                self.defect_id,
                self.fields_widget.get_form_data(),
            )
        )
        if save_error is not None:
            severity, title, exc = save_error
            show = QMessageBox.warning if severity == "warning" else QMessageBox.critical
            show(self, title, str(exc))
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
