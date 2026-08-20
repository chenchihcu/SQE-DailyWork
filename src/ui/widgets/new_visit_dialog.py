from __future__ import annotations

import logging

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database.product_stage import (
    PRODUCT_STAGE_MASS_PRODUCTION,
    PRODUCT_STAGE_OPTIONS,
    normalize_product_stage_ui,
)
from services.appearance_preferences_service import load_application_preferences
from services.event import _visit_service
from ui.layout_constants import (
    ANOMALY_DIALOG_PREFERRED_HEIGHT,
    ANOMALY_DIALOG_PREFERRED_WIDTH,
    DIALOG_OUTER_MARGINS,
    FORM_HORIZONTAL_SPACING,
    FORM_MAX_WIDTH,
    INLINE_SPACING,
    REF_GRID_SPACING_H,
    REF_GRID_SPACING_V,
    VISIT_FORM_CONTENT_SPACING,
    VISIT_FORM_VERTICAL_SPACING,
    VISIT_SUMMARY_VISIBLE_ROWS,
)
from ui.window_sizing import fit_dialog_to_available_screen
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
    VISIT_TIME_SLOT_OPTIONS,
    TechTransferCard,
    VISIT_TECH_TRANSFER_ITEMS,
    apply_dialog_layout,
    set_combo_current_text,
    set_text_edit_visible_rows,
    set_tone,
    style_dialog_buttons,
)
from ui.widgets.visit_tech_transfer_mixin import _VisitTechTransferMixin

logger = logging.getLogger(__name__)


class NewVisitDialog(DirtyTrackingMixin, QDialog, SupplierProductFormMixin, _VisitTechTransferMixin):
    """Shared visit form shell for modal edit/preview and embedded create pages."""

    form_saved = Signal(str)

    def __init__(
        self,
        parent=None,
        *,
        visit_id: str | None = None,
        initial_data: dict | None = None,
        read_only: bool = False,
        embedded: bool = False,
        page_mode: bool = False,
    ):
        super().__init__(parent)
        self._embedded = embedded
        self._page_mode = bool(page_mode)
        if self._page_mode and not self._embedded:
            raise ValueError("page_mode requires embedded=True")
        if self._embedded:
            self.setWindowFlags(Qt.WindowType.Widget)
        self._visit_id = (visit_id or "").strip()
        self._is_edit = bool(self._visit_id)
        self._read_only = read_only
        self._initial_data = initial_data or {}
        self._product_stage_by_id: dict[str, str] = {}
        self._product_code_by_id: dict[str, str] = {}
        self._preserved_visit_defect_notes: list[dict] = []
        self._preserved_product_sections: list[dict] = []
        self._tech_transfer_groups: dict[str, QButtonGroup] = {}
        self._tech_transfer_cards: dict[str, TechTransferCard] = {}
        self._syncing_tech_transfer = False
        self._fixed_visit_id = str(self._initial_data.get("visit_id") or "").strip()
        self.setModal(True)
        self.setMinimumWidth(760)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        self.setWindowTitle("預覽訪廠" if self._read_only else ("編輯訪廠" if self._is_edit else "新增訪廠"))
        self._setup_ui()
        self._load_suppliers()
        if self._is_edit:
            self._apply_initial_data()
        if self._read_only:
            self._apply_read_only()

        if not self._read_only:
            self._connect_dirty_signals()

    def _setup_ui(self):
        prefs = load_application_preferences()
        # 1. 控制項初始化
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setAccessibleName("訪廠日期")
        self.supplier_combo = QComboBox()
        self.supplier_combo.currentIndexChanged.connect(self._on_supplier_changed)
        self.supplier_combo.setAccessibleName("供應商")
        self.product_combo = QComboBox()
        self.product_combo.currentIndexChanged.connect(self._on_product_changed)
        self.product_combo.setAccessibleName("主要產品")
        self.product_stage_combo = QComboBox()
        self.product_stage_combo.addItems(PRODUCT_STAGE_OPTIONS)
        self.product_stage_combo.setCurrentText(PRODUCT_STAGE_MASS_PRODUCTION)
        self.product_stage_combo.setEnabled(False)
        self.product_stage_combo.setAccessibleName("產品階段")
        self.product_code_input = QLineEdit()
        self.product_code_input.setReadOnly(True)
        self.product_code_input.setPlaceholderText("由產品自動帶出")
        self.product_code_input.setAccessibleName("產品代碼/料號")
        self.visitor_input = QLineEdit()  # Retained headless for legacy accessor safety
        self.visitor_input.setPlaceholderText("訪廠人員")
        self.visitor_input.setAccessibleName("訪廠人員")
        self.summary_input = QTextEdit()
        self.summary_input.setPlaceholderText("活動摘要（選填）")
        self.summary_input.setAccessibleName("活動摘要")
        set_text_edit_visible_rows(self.summary_input, VISIT_SUMMARY_VISIBLE_ROWS)

        self.work_order_input = QLineEdit()
        self.work_order_input.setPlaceholderText("輸入工單號碼")
        self.work_order_input.setAccessibleName("工單號碼")
        self.time_slot_input = QComboBox()
        self.time_slot_input.addItems(VISIT_TIME_SLOT_OPTIONS)
        self.time_slot_input.setAccessibleName("時段")
        self.time_slot_input.setText = lambda text: set_combo_current_text(self.time_slot_input, text)  # type: ignore[attr-defined]
        self.time_slot_input.text = lambda: self.time_slot_input.currentText().strip()  # type: ignore[attr-defined]
        self.time_slot_input.setReadOnly = lambda ro: self.time_slot_input.setEnabled(not ro)  # type: ignore[attr-defined]
        if not self._is_edit and not self._initial_data and prefs.default_visit_time_slot:
            set_combo_current_text(self.time_slot_input, prefs.default_visit_time_slot)
        self.qty_input = QLineEdit()
        self.qty_input.setPlaceholderText("輸入訪廠抽樣數量")
        self.qty_input.setAccessibleName("抽樣數量")
        self.qty_input.setValidator(QIntValidator(0, 10_000_000))
        self.tech_transfer_check = QCheckBox("已技轉")
        self.tech_transfer_check.toggled.connect(self._on_tech_transfer_toggled)

        # 2. 固定欄位表單直接參與對話框佈局，避免整頁捲軸壓縮可用寬度。
        self.form_content = QWidget()
        self.form_content.setObjectName("VisitFormContent")
        content_layout = QVBoxLayout(self.form_content)
        content_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        content_layout.setSpacing(VISIT_FORM_CONTENT_SPACING)

        basic_title = QLabel("📋 基本資訊")
        basic_title.setProperty("role", "sectionTitle")
        content_layout.addWidget(basic_title)
        form = QFormLayout()
        form.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        form.setVerticalSpacing(VISIT_FORM_VERTICAL_SPACING)

        product_row = QWidget()
        pr_layout = QHBoxLayout(product_row)
        pr_layout.setContentsMargins(0, 0, 0, 0)
        pr_layout.setSpacing(INLINE_SPACING)
        pr_layout.addWidget(self.product_combo, 3)
        pr_layout.addWidget(self.product_stage_combo, 1)

        self.visitor_input.setVisible(False)
        form.addRow(
            make_paired_form_row(
                "VisitBasicDateTimeSlotRow",
                RequiredFieldLabel("日期"),
                self.date_edit,
                "時段",
                self.time_slot_input,
            )
        )
        form.addRow(RequiredFieldLabel("供應商"), self.supplier_combo)
        form.addRow("主要產品", product_row)
        form.addRow(
            make_paired_form_row(
                "VisitProductCodeWorkOrderRow",
                "料號",
                self.product_code_input,
                "工單",
                self.work_order_input,
            )
        )
        form.addRow(
            make_paired_form_row(
                "VisitQtyTechTransferRow",
                "抽樣數量",
                self.qty_input,
                None,
                self.tech_transfer_check,
            )
        )

        self._product_guard_label = QLabel("")
        self._product_guard_label.setProperty("role", "messageText")
        self._product_guard_label.setVisible(False)
        form.addRow("", self._product_guard_label)

        details_grid = QGridLayout()
        details_grid.setContentsMargins(0, 0, 0, 0)
        details_grid.setHorizontalSpacing(FORM_HORIZONTAL_SPACING)
        details_grid.addLayout(form, 0, 0)

        secondary_layout = QVBoxLayout()
        secondary_layout.setContentsMargins(0, 0, 0, 0)
        secondary_layout.setSpacing(8)
        secondary_layout.addWidget(QLabel("📝 活動摘要"))
        secondary_layout.addWidget(self.summary_input, 1)
        details_grid.addLayout(secondary_layout, 0, 1)
        details_grid.setColumnStretch(0, 1)
        details_grid.setColumnStretch(1, 1)
        content_layout.addLayout(details_grid)

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

        tech_title = QLabel("⚙️ 技轉查核")
        tech_title.setProperty("role", "sectionTitle")
        content_layout.addWidget(tech_title)
        content_layout.addWidget(cards_container)
        content_layout.addStretch(1)
        # 3. 對話框保留固定 footer；全頁建立模式把命令列交由
        # EventCreatePage/CreateWorkflowShell 持有，避免重複的儲存動作。
        self.page_content: QWidget | None = None
        self.form_scroll: QScrollArea | None = None
        if self._page_mode:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.form_content)
            # The page shell scrolls this widget; keep form_content parented to
            # the form so its layout and field ownership remain intact.
            self.page_content = self
            self.save_button = None
            self._button_box = None
            return

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self.save_button = style_dialog_buttons(buttons)
        if self.save_button:
            self.save_button.setCursor(Qt.PointingHandCursor)
            self.save_button.setAccessibleName("儲存訪廠紀錄")
        self._button_box = buttons
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)

        # The modal edit dialog intentionally keeps this compact, fixed form
        # topology. The full-page create surface has less usable height once
        # the shell header and outer margins are present—especially at higher
        # DPI or with enlarged application text. Give only the embedded form a
        # vertical viewport so every field remains reachable while the shared
        # Save/Cancel row stays fixed below it.
        layout_content: QWidget = self.form_content
        if self._embedded:
            self.form_scroll = QScrollArea()
            self.form_scroll.setObjectName("EmbeddedVisitFormScroll")
            self.form_scroll.setWidgetResizable(True)
            self.form_scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self.form_scroll.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            self.form_scroll.setWidget(self.form_content)
            layout_content = self.form_scroll

        apply_dialog_layout(self, layout_content, buttons)
        fit_dialog_to_available_screen(
            self,
            preferred_width=ANOMALY_DIALOG_PREFERRED_WIDTH,
            preferred_height=ANOMALY_DIALOG_PREFERRED_HEIGHT,
            maximum_width=FORM_MAX_WIDTH,
        )
        self._setup_tab_order()

    def _setup_tab_order(self) -> None:
        """Tab follows visual reading order across fields, summary and cards."""
        order = [
            self.date_edit,
            self.time_slot_input,
            self.supplier_combo,
            self.product_combo,
            self.work_order_input,
            self.qty_input,
            self.tech_transfer_check,
            self.summary_input,
        ]
        for card in self._tech_transfer_cards.values():
            if hasattr(card, "yes_radio"):
                order.append(card.yes_radio)
            if hasattr(card, "no_radio"):
                order.append(card.no_radio)

        if self._button_box is not None:
            save_btn = self._button_box.button(QDialogButtonBox.StandardButton.Save)
            cancel_btn = self._button_box.button(QDialogButtonBox.StandardButton.Cancel)
            if save_btn is not None:
                order.append(save_btn)
            if cancel_btn is not None:
                order.append(cancel_btn)

        valid_widgets = [w for w in order if w is not None]
        for earlier, later in zip(valid_widgets, valid_widgets[1:], strict=False):
            self.setTabOrder(earlier, later)

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
        self.time_slot_input.setEnabled(False)
        self.qty_input.setReadOnly(True)
        self.tech_transfer_check.setEnabled(False)
        # Tech transfer cards
        for card in self._tech_transfer_cards.values():
            card.yes_radio.setEnabled(False)
            card.no_radio.setEnabled(False)
            card.na_radio.setEnabled(False)

        # Change Save button to Close and hide Cancel (redundant in read-only mode)
        if self.save_button and self._button_box is not None:
            self.save_button.setText("關閉")
            self._button_box.accepted.disconnect(self._on_submit)
            self._button_box.accepted.connect(self.accept)
        cancel_btn = (
            self._button_box.button(QDialogButtonBox.StandardButton.Cancel)
            if self._button_box is not None
            else None
        )
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
            self.time_slot_input.currentTextChanged,
            self.qty_input.textChanged,
            self.tech_transfer_check.toggled,
        ])

    def _on_supplier_changed_post(self, supplier_id: str, products: list[dict]) -> None:
        self._refresh_submit_state()

    def _on_product_changed_post(self) -> None:
        self._refresh_submit_state()

    def can_submit(self) -> bool:
        """Return the established page/dialog eligibility without duplicating it."""
        return bool((self.supplier_combo.currentData() or "").strip())

    def _refresh_submit_state(self) -> None:
        supplier_id = (self.supplier_combo.currentData() or "").strip()
        product_id = (self.product_combo.currentData() or "").strip()
        has_products = self.product_combo.count() > 1
        message = ""
        tone = "info"
        if not supplier_id:
            message = "請先選擇供應商。"
        elif not has_products and not product_id:
            message = "此供應商尚未建立產品；請先到基礎資料建立產品。"
            tone = "info"
            tone = "info"
        elif not product_id:
            message = "請選擇主要產品。"
        self._product_guard_label.setText(message)
        set_tone(self._product_guard_label, tone)
        self._product_guard_label.setVisible(bool(message))
        if self.save_button is not None:
            self.save_button.setEnabled(self.can_submit())

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
        set_combo_current_text(
            self.time_slot_input, str(self._initial_data.get("time_slot") or "")
        )
        self.qty_input.setText(str(self._initial_data.get("production_qty") or ""))
        sections = list(self._initial_data.get("product_sections") or [])
        self._preserved_visit_defect_notes = [
            item
            for item in list(self._initial_data.get("defect_notes") or [])
            if not str(item.get("visit_product_section_id") or "").strip()
        ]
        self._preserved_product_sections = sections
        if sections:
            first_section = sections[0]
            section_time = str(first_section.get("time_slot") or "").strip()
            if section_time:
                set_combo_current_text(self.time_slot_input, section_time)
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
            visit_level_notes = list(self._preserved_visit_defect_notes)
            primary_notes = (
                list(self._preserved_product_sections[0].get("defect_notes") or [])
                if self._preserved_product_sections
                else []
            )
            product_sections: list[dict] = []
            if (
                product_id
                or self.time_slot_input.currentText().strip()
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
                        "time_slot": self.time_slot_input.currentText().strip(),
                        "work_order_no": self.work_order_input.text().strip(),
                        "production_qty": int(self.qty_input.text().strip() or 0),
                        "summary": "",
                        "defect_notes": primary_notes,
                        "sort_order": 0,
                    }
                )
            product_sections.extend(
                dict(section) for section in self._preserved_product_sections[1:]
            )
            if not product_sections and not visit_level_notes:
                QMessageBox.warning(
                    self,
                    "驗證失敗",
                    "請選擇主要產品。",
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
            "time_slot": self.time_slot_input.currentText().strip(),
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
                completion_text = "訪廠紀錄已更新"
            else:
                _visit_service.create_visit(payload)
                completion_text = "訪廠紀錄已完成"
            self._dirty = False
            if self._embedded:
                self.form_saved.emit(completion_text)
            else:
                QMessageBox.information(self, "成功", localize_popup_message(completion_text))
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
