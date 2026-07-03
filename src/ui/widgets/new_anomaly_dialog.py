from __future__ import annotations

import logging

from PySide6.QtCore import QDate, Qt, QRegularExpression
from PySide6.QtGui import QIntValidator, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database.product_stage import (
    PRODUCT_STAGE_MASS_PRODUCTION,
    PRODUCT_STAGE_OPTIONS,
    normalize_product_stage_ui,
)
from services import event_service
from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    FORM_MAX_WIDTH,
    GRID_GUTTER,
    GROUPBOX_CONTENT_MARGINS,
    INLINE_SPACING,
    REF_CELL_MARGINS,
    REF_GRID_SPACING_H,
    REF_GRID_SPACING_V,
    ROW_GAP,
)
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.widgets.close_anomaly_dialog import AttachmentEditor
from ui.widgets.common_widgets import (
    DirtyTrackingMixin,
    RequiredFieldLabel,
    SupplierProductFormMixin,
)
from ui.widgets.anomaly_visit_sync_mixin import _AnomalyVisitSyncMixin
from ui.widgets.defect_form_widgets import (
    ANOMALY_CATEGORY_OPTIONS,
    ANOMALY_TECH_REF_CARD_DEFS,
    TECH_TRANSFER_STATE_NA,
    TECH_TRANSFER_STATE_NO,
    TECH_TRANSFER_STATE_YES,
    apply_dialog_layout,
    set_combo_current_text,
    set_text_edit_visible_rows,
    set_tone,
    style_dialog_buttons,
)

logger = logging.getLogger(__name__)


class NewAnomalyDialog(DirtyTrackingMixin, QDialog, SupplierProductFormMixin, _AnomalyVisitSyncMixin):
    def __init__(
        self,
        parent=None,
        *,
        anomaly_id: str | None = None,
        initial_data: dict | None = None,
        read_only: bool = False,
    ):
        super().__init__(parent)
        self._anomaly_id = (anomaly_id or "").strip()
        self._is_edit = bool(self._anomaly_id)
        self._read_only = read_only
        self._initial_data = initial_data or {}
        self._fixed_anomaly_no = str(self._initial_data.get("anomaly_no") or "").strip()
        self._product_stage_by_id: dict[str, str] = {}
        self._product_code_by_id: dict[str, str] = {}
        self._ref_data_labels: dict[str, QLabel] = {}
        self._same_day_visit_autofill: dict[str, object] = {
            "product_id": "",
            "work_order_no": "",
            "batch_qty": None,
        }
        self.setWindowTitle("預覽異常" if self._read_only else ("編輯異常" if self._is_edit else "新增異常"))
        self.setMinimumWidth(760)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        self._setup_ui()
        self._load_suppliers()
        if self._is_edit:
            self._apply_initial_data()
        if self._read_only:
            self._apply_read_only()

        if not self._read_only:
            self._connect_dirty_signals()

    def _setup_ui(self):
        # 1. 初始化所有控制項 (保持不變)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._on_date_changed)

        self.anomaly_no_preview_input = QLineEdit()
        self.anomaly_no_preview_input.setMaxLength(11)
        self.anomaly_no_preview_input.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"^\d{0,11}$"))
        )

        self.supplier_combo = QComboBox()
        self.supplier_combo.currentIndexChanged.connect(self._on_supplier_changed)

        self.product_combo = QComboBox()
        self.product_combo.currentIndexChanged.connect(self._on_product_changed)
        self.product_stage_combo = QComboBox()
        self.product_stage_combo.addItems(PRODUCT_STAGE_OPTIONS)
        self.product_stage_combo.setCurrentText(PRODUCT_STAGE_MASS_PRODUCTION)
        self.product_stage_combo.setEnabled(False)

        self.product_code_input = QLineEdit()
        self.product_code_input.setReadOnly(True)
        self.product_code_input.setPlaceholderText("選取產品後自動帶入")

        self.outsource_work_order_input = QLineEdit()
        self.batch_qty_input = QLineEdit()
        self.batch_qty_input.setValidator(QIntValidator(0, 10_000_000))
        self.responsible_person_input = QLineEdit()

        self.due_date_check = QCheckBox("啟用")
        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDate(QDate.currentDate().addDays(7))
        self.due_date_edit.setEnabled(False)
        self.due_date_check.toggled.connect(self.due_date_edit.setEnabled)

        self.is_tech_transfer_check = QCheckBox("技轉訪廠")
        self.category_input = QComboBox()
        self.category_input.setEditable(True)
        self.category_input.addItems(ANOMALY_CATEGORY_OPTIONS)

        self.problem_input = QTextEdit()
        self.problem_input.setPlaceholderText("輸入不良現象、異常描述與補充說明（必填）")
        set_text_edit_visible_rows(self.problem_input, 7)

        self.pending_items_input = QTextEdit()
        self.pending_items_input.setPlaceholderText("確認事項（選填，每行一項）")
        set_text_edit_visible_rows(self.pending_items_input, 4)

        self.sync_visit_check = QCheckBox("同步建立訪廠紀錄")
        self.sync_visit_check.setChecked(True)
        self.sync_visit_check.setVisible(not self._is_edit)
        self._sync_visit_hint_label = QLabel("")
        self._sync_visit_hint_label.setProperty("role", "messageText")
        self._sync_visit_hint_label.setProperty("tone", "info")
        self._sync_visit_hint_label.setVisible(not self._is_edit)
        self.sync_visit_check.toggled.connect(self._update_sync_visit_hint)
        self.date_edit.dateChanged.connect(lambda _d: self._update_sync_visit_hint())

        # 2. 建立分頁系統
        self.tabs = QTabWidget()
        self.tabs.setObjectName("AnomalyFormTabs")

        # --- Tab 1: 基本資訊 ---
        tab_basic = QWidget()
        basic_layout = QVBoxLayout(tab_basic)
        basic_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)

        grid = QGridLayout()
        grid.setHorizontalSpacing(GRID_GUTTER)
        grid.setVerticalSpacing(ROW_GAP)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(4, 1)
        grid.setColumnStretch(5, 1)

        _LEFT_TOP = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        grid.addWidget(RequiredFieldLabel("供應商"), 0, 0)
        grid.addWidget(self.supplier_combo, 0, 1, 1, 2)
        grid.addWidget(RequiredFieldLabel("日期"), 0, 3)
        grid.addWidget(self.date_edit, 0, 4)
        grid.addWidget(self.is_tech_transfer_check, 0, 5)

        product_row = QWidget()
        pr_layout = QHBoxLayout(product_row)
        pr_layout.setContentsMargins(0, 0, 0, 0)
        pr_layout.setSpacing(INLINE_SPACING)
        pr_layout.addWidget(self.product_combo, 3)
        pr_layout.addWidget(self.product_stage_combo, 1)

        grid.addWidget(RequiredFieldLabel("品名"), 1, 0)
        grid.addWidget(product_row, 1, 1, 1, 2)
        grid.addWidget(QLabel("料號"), 1, 3)
        grid.addWidget(self.product_code_input, 1, 4, 1, 2)

        grid.addWidget(QLabel("異常類別"), 2, 0)
        grid.addWidget(self.category_input, 2, 1, 1, 2)
        grid.addWidget(QLabel("數量"), 2, 3)
        grid.addWidget(self.batch_qty_input, 2, 4, 1, 2)

        self._lbl_order = QLabel("委外工單")
        grid.addWidget(self._lbl_order, 3, 0)
        grid.addWidget(self.outsource_work_order_input, 3, 1, 1, 2)
        grid.addWidget(QLabel("責任人"), 3, 3)
        grid.addWidget(self.responsible_person_input, 3, 4, 1, 2)

        due_row = QWidget()
        dr_layout = QHBoxLayout(due_row)
        dr_layout.setContentsMargins(0, 0, 0, 0)
        dr_layout.setSpacing(INLINE_SPACING)
        dr_layout.addWidget(self.due_date_check)
        dr_layout.addWidget(self.due_date_edit, 1)
        grid.addWidget(QLabel("異常單號"), 4, 0)
        grid.addWidget(self.anomaly_no_preview_input, 4, 1, 1, 2)
        grid.addWidget(QLabel("預計回覆日"), 4, 3)
        grid.addWidget(due_row, 4, 4, 1, 2)

        basic_layout.addLayout(grid)
        self._product_guard_label = QLabel("")
        self._product_guard_label.setProperty("role", "messageText")
        self._product_guard_label.setVisible(False)
        basic_layout.addWidget(self._product_guard_label)
        basic_layout.addWidget(self.sync_visit_check)
        basic_layout.addWidget(self._sync_visit_hint_label)

        self._same_day_visit_hint_label = QLabel("")
        self._same_day_visit_hint_label.setProperty("role", "messageText")
        self._same_day_visit_hint_label.setProperty("tone", "info")
        self._same_day_visit_hint_label.setWordWrap(True)
        self._same_day_visit_hint_label.setVisible(False)
        basic_layout.addWidget(self._same_day_visit_hint_label)

        basic_layout.addStretch(1)
        self.tabs.addTab(tab_basic, "基本資訊")

        # --- Tab 2: 異常描述 ---
        tab_desc = QWidget()
        desc_layout = QVBoxLayout(tab_desc)
        desc_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        desc_layout.setSpacing(8)
        desc_layout.addWidget(RequiredFieldLabel("不良現象描述"))
        desc_layout.addWidget(self.problem_input)
        desc_layout.addWidget(QLabel("確認事項 / 待追蹤"))
        desc_layout.addWidget(self.pending_items_input)
        self.tabs.addTab(tab_desc, "問題描述")

        # --- Tab 3: 風險與參考 ---
        tab_ref = QWidget()
        ref_root = QVBoxLayout(tab_ref)
        ref_root.setContentsMargins(*DIALOG_OUTER_MARGINS)
        ref_root.setSpacing(12)

        # 技轉參考
        self._ref_group = QGroupBox("最近技轉訪廠參考")
        ref_layout = QVBoxLayout(self._ref_group)
        ref_layout.setContentsMargins(*GROUPBOX_CONTENT_MARGINS)
        self._linked_visit_label = QLabel("")
        self._linked_visit_label.setProperty("role", "messageText")
        self._linked_visit_label.setWordWrap(True)
        self._linked_visit_label.setVisible(False)
        self.link_visit_button = QPushButton("關聯 / 變更訪廠紀錄…")
        self.link_visit_button.clicked.connect(self._on_link_visit_clicked)
        self.unlink_visit_button = QPushButton("取消連結")
        self.unlink_visit_button.setProperty("tone", "warning")
        self.unlink_visit_button.setVisible(False)
        self.unlink_visit_button.clicked.connect(self._on_unlink_visit_clicked)
        link_row = QHBoxLayout()
        link_row.addWidget(self.link_visit_button, 3)
        link_row.addWidget(self.unlink_visit_button, 1)
        ref_layout.addWidget(self._linked_visit_label)
        ref_layout.addLayout(link_row)

        self._ref_header_label = QLabel("請先選擇供應商以載入技轉參考資料")
        self._ref_header_label.setProperty("role", "messageText")
        self._ref_header_label.setWordWrap(True)
        ref_layout.addWidget(self._ref_header_label)

        ref_cards_widget = QWidget()
        ref_cards_grid = QGridLayout(ref_cards_widget)
        ref_cards_grid.setContentsMargins(0, 0, 0, 0)
        ref_cards_grid.setHorizontalSpacing(REF_GRID_SPACING_H)
        ref_cards_grid.setVerticalSpacing(REF_GRID_SPACING_V)
        for idx, (field_key, field_label) in enumerate(ANOMALY_TECH_REF_CARD_DEFS):
            cell = QFrame()
            cell.setObjectName("refDataCard")
            cl = QHBoxLayout(cell)
            cl.setContentsMargins(*REF_CELL_MARGINS)
            val_lbl = QLabel("—")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cl.addWidget(QLabel(field_label), 1)
            cl.addWidget(val_lbl)
            ref_cards_grid.addWidget(cell, idx // 3, idx % 3)
            self._ref_data_labels[field_key] = val_lbl
        ref_layout.addWidget(ref_cards_widget)
        ref_root.addWidget(self._ref_group)

        # 風險調查
        self._rc_group = QGroupBox("風險控管調查")
        rc_layout = QGridLayout(self._rc_group)
        rc_layout.setContentsMargins(*GROUPBOX_CONTENT_MARGINS)
        rc_options = ["未確認", "已確認", "不適用"]
        self.rc_supplier_inv_combo = QComboBox()
        self.rc_supplier_inv_combo.addItems(rc_options)
        self.rc_supplier_wip_combo = QComboBox()
        self.rc_supplier_wip_combo.addItems(rc_options)
        self.rc_in_transit_combo = QComboBox()
        self.rc_in_transit_combo.addItems(rc_options)
        self.rc_internal_inv_combo = QComboBox()
        self.rc_internal_inv_combo.addItems(rc_options)
        rc_layout.addWidget(QLabel("供應商廠內庫存"), 0, 0)
        rc_layout.addWidget(self.rc_supplier_inv_combo, 0, 1)
        rc_layout.addWidget(QLabel("供應商在線生產"), 0, 2)
        rc_layout.addWidget(self.rc_supplier_wip_combo, 0, 3)
        rc_layout.addWidget(QLabel("在途風險"), 1, 0)
        rc_layout.addWidget(self.rc_in_transit_combo, 1, 1)
        rc_layout.addWidget(QLabel("公司廠內庫存"), 1, 2)
        rc_layout.addWidget(self.rc_internal_inv_combo, 1, 3)
        ref_root.addWidget(self._rc_group)
        ref_root.addStretch(1)
        self.tabs.addTab(tab_ref, "風險與參考")

        # --- Tab 4: 現場照片 ---
        tab_photo = QWidget()
        photo_layout = QVBoxLayout(tab_photo)
        photo_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        self.attachment_editor = AttachmentEditor(self)
        photo_layout.addWidget(self.attachment_editor)
        self.tabs.addTab(tab_photo, "現場照片")

        # 3. 按鈕與對話框佈局
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self.save_button = style_dialog_buttons(buttons)
        self._button_box = buttons
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)

        apply_dialog_layout(self, self.tabs, buttons)
        self._update_anomaly_no_preview()
        self.product_stage_combo.currentTextChanged.connect(
            lambda _: self._update_outsource_row_visibility()
        )
        self.is_tech_transfer_check.toggled.connect(self._update_ref_group_visibility)
        self._update_outsource_row_visibility()
        self._update_ref_group_visibility()

    def _update_outsource_row_visibility(self) -> None:
        """委外工單列只在委外階段或已有值時顯示。"""
        stage = self.product_stage_combo.currentText()
        show = (
            stage == "委外"
            or bool(self.outsource_work_order_input.text().strip())
        )
        self._lbl_order.setVisible(show)
        self.outsource_work_order_input.setVisible(show)

    def _update_ref_group_visibility(self) -> None:
        """技轉參考資料群組只在勾選技轉訪廠時顯示。"""
        checked = self.is_tech_transfer_check.isChecked()
        self._ref_group.setVisible(checked)
        if checked and not self._is_edit:
            self.sync_visit_check.setChecked(True)

    def _apply_read_only(self) -> None:
        """Disable all input widgets to prevent modification."""
        self.date_edit.setEnabled(False)
        self.supplier_combo.setEnabled(False)
        self.product_combo.setEnabled(False)
        self.product_stage_combo.setEnabled(False)
        self.outsource_work_order_input.setReadOnly(True)
        self.batch_qty_input.setReadOnly(True)
        self.category_input.setEnabled(False)
        self.responsible_person_input.setReadOnly(True)
        self.due_date_check.setEnabled(False)
        self.due_date_edit.setEnabled(False)
        self.is_tech_transfer_check.setEnabled(False)
        self.problem_input.setReadOnly(True)
        self.pending_items_input.setReadOnly(True)
        self.anomaly_no_preview_input.setReadOnly(True)

        # Risk control combos
        self.rc_supplier_inv_combo.setEnabled(False)
        self.rc_supplier_wip_combo.setEnabled(False)
        self.rc_in_transit_combo.setEnabled(False)
        self.rc_internal_inv_combo.setEnabled(False)

        # Hide sync visit options in preview
        self.sync_visit_check.setVisible(False)
        self._sync_visit_hint_label.setVisible(False)

        # Link visit buttons
        self.link_visit_button.setEnabled(False)
        self.unlink_visit_button.setEnabled(False)

        # Attachment editor
        self.attachment_editor.set_read_only(True)

        # Change Save button to Close and hide Cancel (redundant in read-only mode)
        if self.save_button:
            self.save_button.setText("關閉")
            # Disconnect from _on_submit and just accept (close)
            self._button_box.accepted.disconnect(self._on_submit)
            self._button_box.accepted.connect(self.accept)
        cancel_btn = self._button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setVisible(False)

    def _connect_dirty_signals(self) -> None:
        self._init_dirty_tracking([
            self.date_edit.dateChanged,
            self.supplier_combo.currentIndexChanged,
            self.product_combo.currentIndexChanged,
            self.product_stage_combo.currentTextChanged,
            self.outsource_work_order_input.textChanged,
            self.batch_qty_input.textChanged,
            self.responsible_person_input.textChanged,
            self.anomaly_no_preview_input.textChanged,
            self.due_date_check.toggled,
            self.due_date_edit.dateChanged,
            self.is_tech_transfer_check.toggled,
            self.category_input.currentTextChanged,
            self.problem_input.textChanged,
            self.pending_items_input.textChanged,
            self.rc_supplier_inv_combo.currentTextChanged,
            self.rc_supplier_wip_combo.currentTextChanged,
            self.rc_in_transit_combo.currentTextChanged,
            self.rc_internal_inv_combo.currentTextChanged,
            self.sync_visit_check.toggled,
            self.attachment_editor.add_button.clicked,
            self.attachment_editor.remove_button.clicked,
        ])

    def _on_date_changed(self, _date: QDate | None = None) -> None:
        self._update_anomaly_no_preview()
        self._apply_same_day_visit_defaults()

    def _update_anomaly_no_preview(self, _date: QDate | None = None):
        anomaly_date = self.date_edit.date().toString("yyyy-MM-dd")
        if self._is_edit:
            original_date = str(self._initial_data.get("anomaly_date") or "").strip()
            if anomaly_date == original_date:
                self.anomaly_no_preview_input.setText(self._fixed_anomaly_no or "")
                return
        try:
            preview = event_service.preview_anomaly_no(anomaly_date)
        except Exception:
            logger.exception("preview_anomaly_no failed for date %s", anomaly_date)
            preview = ""
        self.anomaly_no_preview_input.setText(preview)

    def _on_supplier_changed_post(self, supplier_id: str, products: list[dict]) -> None:
        self._product_items = products
        self._refresh_submit_state()
        self._load_tech_transfer_ref(supplier_id)
        self._apply_same_day_visit_defaults()

    def _load_tech_transfer_ref(self, supplier_id: str) -> None:
        """查詢該供應商最新技轉訪廠資料並更新參考資料卡片。"""
        # 重置所有 label
        for lbl in self._ref_data_labels.values():
            lbl.setText("—")
            lbl.setProperty("status", "muted")
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)
        if not supplier_id:
            self._ref_header_label.setText("請先選擇供應商以載入技轉參考資料")
            return
        try:
            ref = event_service.get_latest_tech_transfer_for_supplier(supplier_id)
        except Exception:
            logger.exception(
                "get_latest_tech_transfer_for_supplier failed for supplier_id=%s",
                supplier_id,
            )
            ref = None
        if ref is None:
            self._ref_header_label.setText("此供應商目前無技轉訪廠紀錄")
            return
        visit_date = str(ref.get("visit_date") or "").strip() or "?"
        self._ref_header_label.setText(f"資料來源：{visit_date} 訪廠紀錄")
        for field_key, _label in ANOMALY_TECH_REF_CARD_DEFS:
            lbl = self._ref_data_labels.get(field_key)
            if lbl is None:
                continue
            if field_key == "tech_transfer":
                has_val = bool(ref.get(field_key, False))
                lbl.setText("是" if has_val else "否")
                lbl.setProperty("status", "success" if has_val else "muted")
            else:
                state_val = (
                    str(ref.get(f"{field_key}_state") or "").strip().lower()
                    or (
                        TECH_TRANSFER_STATE_YES
                        if bool(ref.get(field_key, False))
                        else TECH_TRANSFER_STATE_NO
                    )
                )
                if state_val == TECH_TRANSFER_STATE_YES:
                    lbl.setText("有")
                    lbl.setProperty("status", "success")
                elif state_val == TECH_TRANSFER_STATE_NA:
                    lbl.setText("不適用")
                    lbl.setProperty("status", "na")
                else:
                    lbl.setText("沒有")
                    lbl.setProperty("status", "muted")
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

    def _on_product_changed_post(self) -> None:
        self._refresh_submit_state()

    def _refresh_submit_state(self) -> None:
        supplier_id = (self.supplier_combo.currentData() or "").strip()
        product_id = (self.product_combo.currentData() or "").strip()
        has_products = self.product_combo.count() > 1
        message = ""
        tone = "info"
        if not supplier_id:
            message = "請先選擇供應商。"
        elif not has_products and not product_id:
            message = "此供應商尚未建立產品，請先到基礎資料新增產品。"
            tone = "warning"
        elif not product_id:
            message = "請選擇產品後再儲存。"
        self._product_guard_label.setText(message)
        set_tone(self._product_guard_label, tone)
        self._product_guard_label.setVisible(bool(message))
        self.save_button.setEnabled(bool(supplier_id and product_id))

    def _apply_initial_data(self):
        anomaly_date = str(self._initial_data.get("anomaly_date") or "").strip()
        parsed_date = QDate.fromString(anomaly_date, "yyyy-MM-dd")
        if parsed_date.isValid():
            self.date_edit.setDate(parsed_date)
        self._fixed_anomaly_no = str(self._initial_data.get("anomaly_no") or "").strip()
        self._update_anomaly_no_preview()

        supplier_id = str(self._initial_data.get("supplier_id") or "").strip()
        supplier_name = str(self._initial_data.get("supplier_name") or "").strip()
        self._apply_existing_combo_value(self.supplier_combo, supplier_id, supplier_name)
        self._on_supplier_changed()

        product_id = str(self._initial_data.get("product_id") or "").strip()
        product_name = str(self._initial_data.get("product_name") or "").strip()
        product_code = str(self._initial_data.get("product_code") or "").strip()
        injected = self._apply_existing_combo_value(self.product_combo, product_id, product_name)
        if injected:
            self._product_stage_by_id[product_id] = normalize_product_stage_ui(
                self._initial_data.get("product_stage")
            )
            self._product_code_by_id[product_id] = product_code

        if product_id:
            # Sync product code display
            self.product_code_input.setText(self._product_code_by_id.get(product_id, product_code))
        else:
            self.product_code_input.clear()
        self.product_stage_combo.setCurrentText(
            normalize_product_stage_ui(self._initial_data.get("product_stage"))
        )

        self.outsource_work_order_input.setText(
            str(self._initial_data.get("outsource_work_order") or "")
        )
        self.batch_qty_input.setText(str(self._initial_data.get("batch_qty") or ""))
        self.problem_input.setPlainText(str(self._initial_data.get("problem_desc") or ""))
        # 唯讀預覽顯示解析後類別(已結案優先 root_cause_category,見 AGENTS.md 對齊規則);
        # 編輯模式必須載入原始 category,否則存檔會把根因值無聲覆寫進 category 欄位。
        if self._read_only:
            category_value = self._initial_data.get("category")
        else:
            category_value = self._initial_data.get("category_raw", self._initial_data.get("category"))
        set_combo_current_text(self.category_input, str(category_value or ""))
        self.responsible_person_input.setText(
            str(self._initial_data.get("responsible_person") or "")
        )
        due_date_value = str(self._initial_data.get("due_date") or "").strip()
        if due_date_value:
            parsed_due = QDate.fromString(due_date_value, "yyyy-MM-dd")
            if parsed_due.isValid():
                self.due_date_check.setChecked(True)
                self.due_date_edit.setDate(parsed_due)
        self.pending_items_input.setPlainText(
            str(self._initial_data.get("pending_items") or "")
        )
        self.is_tech_transfer_check.setChecked(
            bool(self._initial_data.get("is_tech_transfer", False))
        )
        self._update_ref_group_visibility()
        self._update_outsource_row_visibility()

        def _get_rc_val(key: str) -> str:
            val = str(self._initial_data.get(key) or "未確認")
            if val == "unconfirmed": return "未確認"
            if val == "confirmed": return "已確認"
            if val == "na": return "不適用"
            return val

        set_combo_current_text(self.rc_supplier_inv_combo, _get_rc_val("rc_supplier_inventory"))
        set_combo_current_text(self.rc_supplier_wip_combo, _get_rc_val("rc_supplier_wip"))
        set_combo_current_text(self.rc_in_transit_combo, _get_rc_val("rc_in_transit"))
        set_combo_current_text(self.rc_internal_inv_combo, _get_rc_val("rc_internal_inventory"))

        self._linked_visit_label.setVisible(False)
        self._linked_visit_label.setText("")

        visit_id = str(self._initial_data.get("visit_id") or "").strip()
        if visit_id:
            self._rc_group.setTitle("風險控管調查 (已關聯訪廠)")
            try:
                v_detail = event_service.get_visit_detail(visit_id)
                v_date = v_detail.get("visit_date") or "?"
                v_summary = (v_detail.get("summary") or "").strip() or "(無摘要)"
                self._linked_visit_label.setText(
                    f"【本單已關聯訪廠紀錄】\n日期：{v_date}\n摘要：{v_summary}"
                )
                self._linked_visit_label.setVisible(True)
                self.unlink_visit_button.setVisible(True)
            except Exception:
                logger.exception("Failed to load linked visit %s", visit_id)
                self._linked_visit_label.setText("【本單已關聯訪廠紀錄】(無法載入詳細資訊)")
                self._linked_visit_label.setVisible(True)
        else:
            self._rc_group.setTitle("風險控管調查 (單獨異常 / 無訪廠紀錄適用)")

        self._refresh_submit_state()
        if self._is_edit:
            self.attachment_editor.load_existing_attachments(self._anomaly_id)

    def _on_submit(self):
        product_id = (self.product_combo.currentData() or "").strip()
        if not product_id:
            QMessageBox.warning(self, "驗證失敗", localize_popup_message("產品為必填"))
            return
        anomaly_no_val = self.anomaly_no_preview_input.text().strip()
        if not anomaly_no_val:
            QMessageBox.warning(self, "驗證失敗", localize_popup_message("異常單號為必填"))
            return
        if not (len(anomaly_no_val) == 11 and anomaly_no_val.isdigit()):
            QMessageBox.warning(
                self,
                "驗證失敗",
                localize_popup_message("異常單號必須為 11 位純數字"),
            )
            return
        
        expected_prefix = self.date_edit.date().toString("yyyyMMdd")
        if not anomaly_no_val.startswith(expected_prefix):
            QMessageBox.warning(
                self,
                "驗證失敗",
                localize_popup_message(f"異常單號前 8 碼必須與所選日期 ({expected_prefix}) 一致"),
            )
            return
            
        due_date_value = ""
        if self.due_date_check.isChecked():
            due_date_value = self.due_date_edit.date().toString("yyyy-MM-dd")
        payload = {
            "anomaly_no": anomaly_no_val,
            "anomaly_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "supplier_id": (self.supplier_combo.currentData() or "").strip(),
            "product_id": product_id,
            "problem_desc": self.problem_input.toPlainText().strip(),
            "category": self.category_input.currentText().strip(),
            "outsource_work_order": self.outsource_work_order_input.text().strip(),
            "batch_qty": int(self.batch_qty_input.text().strip() or 0),
            "responsible_person": self.responsible_person_input.text().strip(),
            "due_date": due_date_value,
            "pending_items": self.pending_items_input.toPlainText().strip(),
            "sync_visit": self.sync_visit_check.isChecked(),
            "visit_summary": "由新增異常流程同步建立。",
            "rc_supplier_inventory": self.rc_supplier_inv_combo.currentText(),
            "rc_supplier_wip": self.rc_supplier_wip_combo.currentText(),
            "rc_in_transit": self.rc_in_transit_combo.currentText(),
            "rc_internal_inventory": self.rc_internal_inv_combo.currentText(),
            "is_tech_transfer": self.is_tech_transfer_check.isChecked(),
        }
        try:
            if self._is_edit:
                event_service.update_anomaly(self._anomaly_id, payload)
                self.attachment_editor.save_to_anomaly(self._anomaly_id)
                self._warn_if_attachment_rename_failures()
                QMessageBox.information(self, "成功", localize_popup_message("異常資料已更新"))
            else:
                result = event_service.create_anomaly_with_visit_link(payload)
                anomaly_id = str(result.get("anomaly_id") or "").strip()
                if anomaly_id:
                    self.attachment_editor.save_to_anomaly(anomaly_id)
                    self._warn_if_attachment_rename_failures()
                visit_action = result.get("visit_action", "none")
                if visit_action == "created":
                    visit_text = "訪廠已新建"
                elif visit_action == "reused":
                    visit_text = "訪廠已重用（同供應商同日期）"
                else:
                    visit_text = "未同步訪廠"
                QMessageBox.information(
                    self,
                    "成功",
                    localize_popup_message(f"已建立異常單：{result['anomaly_no']}\n{visit_text}"),
                )
            self._dirty = False
            self.accept()
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", localize_exception(exc))
        except Exception as exc:
            logger.exception("建立異常失敗")
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"建立異常失敗：{localize_exception(exc)}"),
            )

    def _warn_if_attachment_rename_failures(self) -> None:
        failures = self.attachment_editor._last_rename_failures
        if failures:
            QMessageBox.warning(
                self,
                "附件改名失敗",
                "以下附件改名未成功，檔名可能維持原狀：\n" + "\n".join(failures),
            )
