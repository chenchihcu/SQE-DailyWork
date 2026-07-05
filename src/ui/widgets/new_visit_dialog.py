from __future__ import annotations

import logging

from PySide6.QtCore import QDate
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
from services.event import _anomaly_service, _visit_service
from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    FORM_HORIZONTAL_SPACING,
    FORM_MAX_WIDTH,
    FORM_VERTICAL_SPACING,
    INLINE_SPACING,
    REF_GRID_SPACING_H,
    REF_GRID_SPACING_V,
    ROW_GAP,
)
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.widgets.common_widgets import (
    DirtyTrackingMixin,
    RequiredFieldLabel,
    SupplierProductFormMixin,
    make_paired_form_row,
)
from ui.widgets.defect_form_widgets import (
    TECH_TRANSFER_STATE_NA,
    TECH_TRANSFER_STATE_NO,
    TECH_TRANSFER_STATE_YES,
    TechTransferCard,
    VISIT_TECH_TRANSFER_ITEMS,
    apply_dialog_layout,
    set_text_edit_visible_rows,
    set_tone,
    style_dialog_buttons,
)
from ui.widgets.defect_note_form_widgets import (
    DefectNoteTable,
    ProductSectionEditor,
)
from ui.widgets.visit_tech_transfer_mixin import _VisitTechTransferMixin

logger = logging.getLogger(__name__)


class NewVisitDialog(DirtyTrackingMixin, QDialog, SupplierProductFormMixin, _VisitTechTransferMixin):
    def __init__(
        self,
        parent=None,
        *,
        visit_id: str | None = None,
        initial_data: dict | None = None,
        read_only: bool = False,
        focus_defect_note: bool = False,
    ):
        super().__init__(parent)
        self._visit_id = (visit_id or "").strip()
        self._is_edit = bool(self._visit_id)
        self._read_only = read_only
        self._initial_data = initial_data or {}
        self._product_stage_by_id: dict[str, str] = {}
        self._product_code_by_id: dict[str, str] = {}
        self._product_items: list[dict] = []
        self._extra_section_editors: list[ProductSectionEditor] = []
        self._focus_defect_note = focus_defect_note
        self._tech_transfer_groups: dict[str, QButtonGroup] = {}
        self._tech_transfer_cards: dict[str, TechTransferCard] = {}
        self._syncing_tech_transfer = False
        self.setWindowTitle("預覽訪廠" if self._read_only else ("編輯訪廠" if self._is_edit else "新增訪廠"))
        self.setMinimumWidth(760)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        self._setup_ui()
        if self._is_edit:
            self.confirm_supplier_anomaly_check.setVisible(False)
        self._load_suppliers()
        if self._is_edit:
            self._apply_initial_data()
        elif self._focus_defect_note:
            self.visit_defect_table.add_empty_note()
            self.tabs.setCurrentIndex(2)
            self.visit_defect_table.setFocus()
        if self._read_only:
            self._apply_read_only()

        if not self._read_only:
            self._connect_dirty_signals()

    def _setup_ui(self):
        # 1. 控制項初始化
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
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
        self.visitor_input = QLineEdit()
        self.visitor_input.setPlaceholderText("訪廠人員（選填）")
        self.summary_input = QTextEdit()
        self.summary_input.setPlaceholderText("活動摘要（選填）")
        set_text_edit_visible_rows(self.summary_input, 5)

        self.work_order_input = QLineEdit()
        self.time_slot_input = QLineEdit()
        self.time_slot_input.setPlaceholderText("上午 / 下午 / 產線時段")
        self.qty_input = QLineEdit()
        self.qty_input.setValidator(QIntValidator(0, 10_000_000))
        self.tech_transfer_check = QCheckBox("已技轉")
        self.tech_transfer_check.toggled.connect(self._on_tech_transfer_toggled)

        # 2. 建立分頁
        self.tabs = QTabWidget()
        self.tabs.setObjectName("VisitFormTabs")

        # --- Tab 1: 基本資訊 ---
        tab_basic = QWidget()
        basic_layout = QVBoxLayout(tab_basic)
        basic_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        form = QFormLayout()
        form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        form.setVerticalSpacing(FORM_VERTICAL_SPACING)

        product_row = QWidget()
        pr_layout = QHBoxLayout(product_row)
        pr_layout.setContentsMargins(0, 0, 0, 0)
        pr_layout.setSpacing(INLINE_SPACING)
        pr_layout.addWidget(self.product_combo, 3)
        pr_layout.addWidget(self.product_stage_combo, 1)

        form.addRow(
            make_paired_form_row(
                "VisitBasicDateVisitorRow",
                RequiredFieldLabel("日期"),
                self.date_edit,
                "訪廠人員",
                self.visitor_input,
            )
        )
        form.addRow(RequiredFieldLabel("供應商"), self.supplier_combo)
        form.addRow("主要產品", product_row)
        form.addRow("料號", self.product_code_input)

        self._product_guard_label = QLabel("")
        self._product_guard_label.setProperty("role", "messageText")
        self._product_guard_label.setVisible(False)
        form.addRow("", self._product_guard_label)
        form.addRow("活動摘要", self.summary_input)
        basic_layout.addLayout(form)
        # 多餘垂直空間導向底部，避免 _product_guard_label 提示框被拉伸成大色塊
        # （與 NewAnomalyDialog 基本資訊分頁一致）。
        basic_layout.addStretch(1)
        self.tabs.addTab(tab_basic, "基本資訊")

        # --- Tab 2: 進階與技轉 ---
        tab_adv = QWidget()
        adv_layout = QVBoxLayout(tab_adv)
        adv_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)

        adv_form = QFormLayout()
        adv_form.addRow(
            make_paired_form_row(
                "VisitAdvancedTimeOrderRow",
                "時段",
                self.time_slot_input,
                "工單",
                self.work_order_input,
            )
        )
        adv_form.addRow(
            make_paired_form_row(
                "VisitAdvancedQtyTransferRow",
                "數量",
                self.qty_input,
                None,
                self.tech_transfer_check,
            )
        )
        adv_layout.addLayout(adv_form)

        cards_container = QWidget()
        cards_grid = QGridLayout(cards_container)
        cards_grid.setContentsMargins(0, 4, 0, 4)
        cards_grid.setHorizontalSpacing(REF_GRID_SPACING_H)
        cards_grid.setVerticalSpacing(REF_GRID_SPACING_V)
        for idx, (field_key, field_label) in enumerate(VISIT_TECH_TRANSFER_ITEMS):
            card = TechTransferCard(field_key, field_label, self)
            card.yes_radio.toggled.connect(self._on_any_tech_transfer_item_toggled)
            cards_grid.addWidget(card, idx // 3, idx % 3)
            self._tech_transfer_cards[field_key] = card
            self._tech_transfer_groups[field_key] = card.group

        adv_layout.addWidget(QLabel("技轉要目確認"))
        adv_layout.addWidget(cards_container)
        adv_layout.addStretch(1)
        self.tabs.addTab(tab_adv, "進階與技轉")

        # --- Tab 3: 輕量缺失紀錄 ---
        tab_defects = QWidget()
        defect_layout = QVBoxLayout(tab_defects)
        defect_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        defect_layout.setSpacing(ROW_GAP)

        visit_defect_group = QGroupBox("訪廠層級缺失（不限定產品）")
        visit_defect_layout = QVBoxLayout(visit_defect_group)
        self.visit_defect_table = DefectNoteTable()
        self.confirm_supplier_anomaly_check = QCheckBox("確認後建立正式供應商異常事件")
        self.confirm_supplier_anomaly_check.setObjectName("VisitConfirmSupplierAnomalyCheck")
        self.confirm_supplier_anomaly_check.setToolTip(
            "僅將訪廠/稽核缺失轉成供應商異常事件，不寫入倉庫不合格品追蹤。"
        )
        visit_defect_buttons = QHBoxLayout()
        self._btn_add_visit_defect = QPushButton("新增缺失")
        self._btn_add_visit_defect.setProperty("variant", "secondary")
        self._btn_add_visit_defect.clicked.connect(self.visit_defect_table.add_empty_note)
        self._btn_remove_visit_defect = QPushButton("刪除缺失")
        self._btn_remove_visit_defect.setProperty("tone", "warning")
        self._btn_remove_visit_defect.clicked.connect(self.visit_defect_table.remove_selected_note)
        visit_defect_buttons.addWidget(self._btn_add_visit_defect)
        visit_defect_buttons.addWidget(self._btn_remove_visit_defect)
        visit_defect_buttons.addStretch(1)
        visit_defect_layout.addWidget(self.visit_defect_table)
        visit_defect_layout.addLayout(visit_defect_buttons)
        visit_defect_layout.addWidget(self.confirm_supplier_anomaly_check)

        primary_defect_group = QGroupBox("主要產品缺失")
        primary_defect_layout = QVBoxLayout(primary_defect_group)
        self.primary_defect_table = DefectNoteTable()
        primary_defect_buttons = QHBoxLayout()
        self._btn_add_primary_defect = QPushButton("新增缺失")
        self._btn_add_primary_defect.setProperty("variant", "secondary")
        self._btn_add_primary_defect.clicked.connect(self.primary_defect_table.add_empty_note)
        self._btn_remove_primary_defect = QPushButton("刪除缺失")
        self._btn_remove_primary_defect.setProperty("tone", "warning")
        self._btn_remove_primary_defect.clicked.connect(self.primary_defect_table.remove_selected_note)
        primary_defect_buttons.addWidget(self._btn_add_primary_defect)
        primary_defect_buttons.addWidget(self._btn_remove_primary_defect)
        primary_defect_buttons.addStretch(1)
        primary_defect_layout.addWidget(self.primary_defect_table)
        primary_defect_layout.addLayout(primary_defect_buttons)

        extra_header = QHBoxLayout()
        extra_header.addWidget(QLabel("其他產品區段"))
        extra_header.addStretch(1)
        self._btn_add_section = QPushButton("新增產品區段")
        self._btn_add_section.setProperty("variant", "secondary")
        self._btn_add_section.clicked.connect(self._add_extra_product_section)
        self._btn_remove_section = QPushButton("刪除最後區段")
        self._btn_remove_section.setProperty("tone", "warning")
        self._btn_remove_section.clicked.connect(self._remove_last_extra_product_section)
        extra_header.addWidget(self._btn_add_section)
        extra_header.addWidget(self._btn_remove_section)
        self.extra_sections_container = QWidget()
        self.extra_sections_layout = QVBoxLayout(self.extra_sections_container)
        self.extra_sections_layout.setContentsMargins(0, 0, 0, 0)
        self.extra_sections_layout.setSpacing(ROW_GAP)

        defect_layout.addWidget(visit_defect_group)
        defect_layout.addWidget(primary_defect_group)
        defect_layout.addLayout(extra_header)
        defect_layout.addWidget(self.extra_sections_container)
        defect_layout.addStretch(1)
        self.tabs.addTab(tab_defects, "缺失紀錄")

        # 3. 按鈕與佈局
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self.save_button = style_dialog_buttons(buttons)
        self._button_box = buttons
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)

        apply_dialog_layout(self, self.tabs, buttons)

    def _apply_read_only(self) -> None:
        """Disable all input widgets to prevent modification."""
        self.date_edit.setEnabled(False)
        self.supplier_combo.setEnabled(False)
        self.product_combo.setEnabled(False)
        self.product_stage_combo.setEnabled(False)
        self.product_code_input.setReadOnly(True)
        self.visitor_input.setReadOnly(True)
        self.summary_input.setReadOnly(True)
        self.work_order_input.setReadOnly(True)
        self.time_slot_input.setReadOnly(True)
        self.qty_input.setReadOnly(True)
        self.tech_transfer_check.setEnabled(False)
        self.visit_defect_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.primary_defect_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.confirm_supplier_anomaly_check.setEnabled(False)
        for editor in self._extra_section_editors:
            editor.set_read_only()

        # Tech transfer cards
        for card in self._tech_transfer_cards.values():
            card.yes_radio.setEnabled(False)
            card.no_radio.setEnabled(False)
            card.na_radio.setEnabled(False)

        # Change Save button to Close and hide Cancel (redundant in read-only mode)
        if self.save_button:
            self.save_button.setText("關閉")
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
            self.visitor_input.textChanged,
            self.summary_input.textChanged,
            self.work_order_input.textChanged,
            self.time_slot_input.textChanged,
            self.qty_input.textChanged,
            self.tech_transfer_check.toggled,
            self.confirm_supplier_anomaly_check.toggled,
            self._btn_add_visit_defect.clicked,
            self._btn_remove_visit_defect.clicked,
            self._btn_add_primary_defect.clicked,
            self._btn_remove_primary_defect.clicked,
            self._btn_add_section.clicked,
            self._btn_remove_section.clicked,
            self.visit_defect_table.itemChanged,
            self.primary_defect_table.itemChanged,
        ])

    def _add_extra_product_section(self, data: dict | None = None) -> ProductSectionEditor:
        editor = ProductSectionEditor(f"產品區段 {len(self._extra_section_editors) + 2}", self)
        editor.set_products(self._product_items)
        if data:
            editor.load_data(data)
        if self._read_only:
            editor.set_read_only()
        self._extra_section_editors.append(editor)
        self.extra_sections_layout.addWidget(editor)
        self._refresh_submit_state()
        return editor

    def _remove_last_extra_product_section(self) -> None:
        if not self._extra_section_editors or self._read_only:
            return
        editor = self._extra_section_editors.pop()
        self.extra_sections_layout.removeWidget(editor)
        editor.deleteLater()
        self._refresh_submit_state()

    def _on_supplier_changed_post(self, supplier_id: str, products: list[dict]) -> None:
        self._product_items = list(products)
        for editor in self._extra_section_editors:
            editor.set_products(products)
        self._refresh_submit_state()

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
            message = "此供應商尚未建立產品；仍可先記錄訪廠層級缺失。"
            tone = "info"
        elif not product_id:
            message = "可選擇主要產品，或直接在缺失紀錄分頁新增訪廠層級缺失。"
        self._product_guard_label.setText(message)
        set_tone(self._product_guard_label, tone)
        self._product_guard_label.setVisible(bool(message))
        if self.save_button is not None:
            self.save_button.setEnabled(bool(supplier_id))

    def _apply_initial_data(self):
        visit_date = str(self._initial_data.get("visit_date") or "").strip()
        parsed_date = QDate.fromString(visit_date, "yyyy-MM-dd")
        if parsed_date.isValid():
            self.date_edit.setDate(parsed_date)

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
            self.product_code_input.setText(self._product_code_by_id.get(product_id, product_code))
        else:
            self.product_code_input.clear()

        self.product_stage_combo.setCurrentText(
            normalize_product_stage_ui(self._initial_data.get("product_stage"))
        )

        self.visitor_input.setText(str(self._initial_data.get("visitor_name") or ""))
        self.summary_input.setPlainText(str(self._initial_data.get("summary") or ""))
        self.work_order_input.setText(str(self._initial_data.get("work_order_no") or ""))
        self.time_slot_input.setText(str(self._initial_data.get("time_slot") or ""))
        self.qty_input.setText(str(self._initial_data.get("production_qty") or ""))
        sections = list(self._initial_data.get("product_sections") or [])
        visit_level_notes = [
            item
            for item in list(self._initial_data.get("defect_notes") or [])
            if not str(item.get("visit_product_section_id") or "").strip()
        ]
        self.visit_defect_table.load_notes(visit_level_notes)
        if sections:
            first_section = sections[0]
            self.primary_defect_table.load_notes(
                list(first_section.get("defect_notes") or [])
            )
            section_time = str(first_section.get("time_slot") or "").strip()
            if section_time:
                self.time_slot_input.setText(section_time)
            section_summary = str(first_section.get("summary") or "").strip()
            if section_time or section_summary:
                prefix = f"[{section_time}] " if section_time else ""
                current_summary = self.summary_input.toPlainText().strip()
                merged = "\n".join(
                    part
                    for part in (current_summary, f"{prefix}{section_summary}".strip())
                    if part
                )
                self.summary_input.setPlainText(merged)
            for section in sections[1:]:
                self._add_extra_product_section(section)
        initial_states: dict[str, str] = {}
        for key, _ in VISIT_TECH_TRANSFER_ITEMS:
            state_val = str(self._initial_data.get(f"{key}_state") or "").strip().lower()
            if state_val in (
                TECH_TRANSFER_STATE_YES,
                TECH_TRANSFER_STATE_NO,
                TECH_TRANSFER_STATE_NA,
            ):
                initial_states[key] = state_val
            else:
                initial_states[key] = (
                    TECH_TRANSFER_STATE_YES
                    if bool(self._initial_data.get(key, False))
                    else TECH_TRANSFER_STATE_NO
                )
        self._apply_tech_transfer_payload(
            tech_transfer=bool(self._initial_data.get("tech_transfer", False)),
            item_states=initial_states,
        )
        self._refresh_submit_state()

    def _on_submit(self):
        product_id = (self.product_combo.currentData() or "").strip()
        try:
            visit_level_notes = self.visit_defect_table.notes()
            primary_notes = self.primary_defect_table.notes()
            product_sections: list[dict] = []
            if (
                product_id
                or self.time_slot_input.text().strip()
                or self.work_order_input.text().strip()
                or self.qty_input.text().strip()
                or primary_notes
            ):
                if not product_id:
                    QMessageBox.warning(self, "驗證失敗", "主要產品區段需選擇品名")
                    return
                product_sections.append(
                    {
                        "product_id": product_id,
                        "product_name": self.product_combo.currentText().strip(),
                        "product_stage": self.product_stage_combo.currentText(),
                        "product_code": self.product_code_input.text().strip(),
                        "time_slot": self.time_slot_input.text().strip(),
                        "work_order_no": self.work_order_input.text().strip(),
                        "production_qty": int(self.qty_input.text().strip() or 0),
                        "summary": "",
                        "defect_notes": primary_notes,
                        "sort_order": 0,
                    }
                )
            for editor in self._extra_section_editors:
                section = editor.section_data()
                if section is not None:
                    section["sort_order"] = len(product_sections)
                    product_sections.append(section)
            if self.confirm_supplier_anomaly_check.isChecked():
                self._validate_supplier_anomaly_conversion(
                    product_id=product_id,
                    visit_level_notes=visit_level_notes,
                    product_sections=product_sections,
                )
            if not product_sections and not visit_level_notes:
                QMessageBox.warning(
                    self,
                    "驗證失敗",
                    "請至少選擇一個產品區段，或新增一筆訪廠層級缺失。",
                )
                return
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", str(exc))
            return
        tech_payload = self._normalized_tech_transfer_payload(
            tech_transfer=self.tech_transfer_check.isChecked(),
            item_states={
                key: self._get_tech_transfer_state(key)
                for key, _ in VISIT_TECH_TRANSFER_ITEMS
            },
        )
        payload = {
            "visit_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "supplier_id": (self.supplier_combo.currentData() or "").strip(),
            "product_id": product_id,
            "visitor_name": self.visitor_input.text().strip(),
            "summary": self.summary_input.toPlainText().strip(),
            "time_slot": self.time_slot_input.text().strip(),
            "work_order_no": self.work_order_input.text().strip(),
            "production_qty": int(self.qty_input.text().strip() or 0),
            "product_sections": product_sections,
            "defect_notes": visit_level_notes,
            "tech_transfer": tech_payload["tech_transfer"],
            "tech_transfer_doc": tech_payload["tech_transfer_doc"],
            "carrier_requirement": tech_payload["carrier_requirement"],
            "dispensing_process": tech_payload["dispensing_process"],
            "functional_test": tech_payload["functional_test"],
            "packaging_requirement": tech_payload["packaging_requirement"],
            "tech_transfer_states": tech_payload["states"],
        }
        try:
            if self._is_edit:
                _visit_service.update_visit(self._visit_id, payload)
                QMessageBox.information(self, "成功", localize_popup_message("訪廠紀錄已更新"))
            else:
                visit_id = _visit_service.create_visit(payload)
                created_anomalies = self._create_confirmed_supplier_anomalies(
                    visit_id=visit_id,
                    payload=payload,
                    visit_level_notes=visit_level_notes,
                    product_sections=product_sections,
                )
                if created_anomalies:
                    QMessageBox.information(
                        self,
                        "成功",
                        localize_popup_message(
                            f"訪廠紀錄已完成，並建立 {created_anomalies} 筆正式供應商異常事件"
                        ),
                    )
                else:
                    QMessageBox.information(self, "成功", localize_popup_message("訪廠紀錄已完成"))
            self._dirty = False
            self.accept()
        except ValueError as exc:
            QMessageBox.warning(self, "驗證失敗", localize_exception(exc))
        except Exception as exc:
            logger.exception("建立訪廠失敗")
            QMessageBox.critical(
                self,
                "錯誤",
                localize_popup_message(f"建立訪廠失敗：{localize_exception(exc)}"),
            )

    def _validate_supplier_anomaly_conversion(
        self,
        *,
        product_id: str,
        visit_level_notes: list[dict],
        product_sections: list[dict],
    ) -> None:
        if not (visit_level_notes or any(section.get("defect_notes") for section in product_sections)):
            return
        if visit_level_notes and not product_id:
            raise ValueError("建立正式供應商異常事件需選擇主要產品。")
        for section in product_sections:
            if section.get("defect_notes") and not str(section.get("product_id") or "").strip():
                raise ValueError("建立正式供應商異常事件需選擇缺失所屬產品。")

    def _create_confirmed_supplier_anomalies(
        self,
        *,
        visit_id: str,
        payload: dict,
        visit_level_notes: list[dict],
        product_sections: list[dict],
    ) -> int:
        if self._is_edit or not self.confirm_supplier_anomaly_check.isChecked():
            return 0
        count = 0
        for note in visit_level_notes:
            _anomaly_service.create_anomaly_with_visit_link(
                {
                    "visit_id": visit_id,
                    "sync_visit": False,
                    "anomaly_date": payload["visit_date"],
                    "supplier_id": payload["supplier_id"],
                    "product_id": payload["product_id"],
                    "product_stage": self.product_stage_combo.currentText(),
                    "problem_desc": note.get("defect_desc", ""),
                    "pending_items": note.get("improvement_desc", ""),
                    "category": "訪廠/稽核缺失",
                    "visit_summary": payload.get("summary", ""),
                }
            )
            count += 1
        for section in product_sections:
            section_product_id = str(section.get("product_id") or "").strip()
            for note in section.get("defect_notes") or []:
                _anomaly_service.create_anomaly_with_visit_link(
                    {
                        "visit_id": visit_id,
                        "sync_visit": False,
                        "anomaly_date": payload["visit_date"],
                        "supplier_id": payload["supplier_id"],
                        "product_id": section_product_id,
                        "product_stage": section.get("product_stage") or PRODUCT_STAGE_MASS_PRODUCTION,
                        "problem_desc": note.get("defect_desc", ""),
                        "pending_items": note.get("improvement_desc", ""),
                        "category": "訪廠/稽核缺失",
                        "outsource_work_order": section.get("work_order_no", ""),
                        "batch_qty": section.get("production_qty", 0),
                        "visit_summary": payload.get("summary", ""),
                    }
                )
                count += 1
        return count
