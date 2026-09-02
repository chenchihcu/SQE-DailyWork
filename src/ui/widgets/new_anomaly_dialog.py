from __future__ import annotations

import logging

from PySide6.QtCore import QDate, Qt, QRegularExpression, Signal
from PySide6.QtGui import QIntValidator, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QButtonGroup,
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
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from database.product_stage import (
    PRODUCT_STAGE_MASS_PRODUCTION,
    PRODUCT_STAGE_OPTIONS,
    normalize_product_stage_ui,
)
from services.anomaly_category_preset_service import all_category_labels, is_valid_category
from services.anomaly_source_preset_service import all_source_labels
from services.appearance_preferences_service import load_application_preferences
from services.anomaly_trace_contract import (
    TRACE_FIELD_LABELS,
    TRACE_FIELD_OUTSOURCE_WORK_ORDER,
    normalize_anomaly_source,
    required_trace_fields_for_source,
    visible_trace_fields_for_source,
)
from services.event import _anomaly_service
from ui.layout_constants import (
    ANOMALY_ATTACHMENT_COMPACT_HEIGHT,
    ANOMALY_DIALOG_PREFERRED_HEIGHT,
    ANOMALY_DIALOG_PREFERRED_WIDTH,
    DIALOG_OUTER_MARGINS,
    FORM_MAX_WIDTH,
    FORM_VERTICAL_SPACING,
    GRID_GUTTER,
    GROUPBOX_CONTENT_MARGINS,
    INLINE_SPACING,
    ROW_GAP,
)
from ui.sidebar_nav import NAV_LABEL_MASTER_SEMI_FINISHED
from ui.window_sizing import fit_dialog_to_available_screen
from ui.popup_i18n import localize_exception, localize_popup_message
from ui.widgets.bullet_list_widget import BulletListWidget
from ui.widgets.tag_input_widget import TagInputWidget
from ui.widgets.close_anomaly_dialog import AttachmentEditor
from ui.widgets.common_widgets import (
    DirtyTrackingMixin,
    RequiredFieldLabel,
    SupplierProductFormMixin,
)
from ui.widgets.defect_form_widgets import (
    apply_dialog_layout,
    set_combo_current_text,
    set_tone,
    style_dialog_buttons,
)

logger = logging.getLogger(__name__)


class NewAnomalyDialog(DirtyTrackingMixin, QDialog, SupplierProductFormMixin):
    form_saved = Signal(str)

    def __init__(
        self,
        parent=None,
        *,
        anomaly_id: str | None = None,
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
        self._anomaly_id = (anomaly_id or "").strip()
        self._is_edit = bool(self._anomaly_id)
        self._read_only = read_only
        self._initial_data = initial_data or {}
        self._fixed_anomaly_no = str(self._initial_data.get("anomaly_no") or "").strip()
        self._product_stage_by_id: dict[str, str] = {}
        self._product_code_by_id: dict[str, str] = {}
        self.setWindowTitle("預覽異常" if self._read_only else ("編輯異常" if self._is_edit else "新增異常"))
        self.setMinimumWidth(760)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        self._setup_ui()
        self._load_suppliers()
        if self._is_edit or self._initial_data:
            self._apply_initial_data()
        if self._read_only:
            self._apply_read_only()

        if not self._read_only:
            self._connect_dirty_signals()

    def _setup_ui(self):
        # 1. 初始化所有控制項 (保持不變)
        prefs = load_application_preferences()
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

        self.anomaly_source_combo = QComboBox()
        self._populate_anomaly_source_combo()
        if not self._is_edit and not self._initial_data and prefs.default_anomaly_source:
            set_combo_current_text(
                self.anomaly_source_combo,
                normalize_anomaly_source(prefs.default_anomaly_source),
            )
        self.anomaly_source_combo.currentTextChanged.connect(
            lambda _: self._update_trace_row_visibility()
        )

        self._trace_labels: dict[str, QLabel] = {}
        self._trace_inputs: dict[str, QLineEdit] = {}
        for field in TRACE_FIELD_LABELS:
            label = QLabel(TRACE_FIELD_LABELS[field])
            line_edit = QLineEdit()
            if prefs.auto_uppercase_part_no:
                line_edit.textChanged.connect(
                    lambda text, widget=line_edit: widget.setText(text.upper())
                    if text != text.upper()
                    else None
                )
            self._trace_labels[field] = label
            self._trace_inputs[field] = line_edit
        self.outsource_work_order_input = self._trace_inputs[TRACE_FIELD_OUTSOURCE_WORK_ORDER]
        self.batch_qty_input = QLineEdit()
        self.batch_qty_input.setValidator(QIntValidator(0, 10_000_000))
        self.responsible_person_input = QLineEdit()
        if not self._is_edit and not self._initial_data and prefs.default_responsible_person:
            self.responsible_person_input.setText(prefs.default_responsible_person)

        self.due_date_check = QCheckBox("啟用")
        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        default_days = prefs.default_due_days if not self._is_edit and not self._initial_data else 7
        self.due_date_edit.setDate(QDate.currentDate().addDays(default_days))
        self.due_date_edit.setEnabled(False)
        self.due_date_check.toggled.connect(self.due_date_edit.setEnabled)

        # QDateEdit's themed minimumSizeHint includes calendar-button padding.
        # Let the grid allocate the available width instead of forcing the
        # scroll content wider than the 760px dialog contract.
        for date_control in (self.date_edit, self.due_date_edit):
            date_control.setMinimumWidth(0)
            date_control.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Fixed,
            )

        self.quality_report_required_group = QButtonGroup(self)
        self.quality_report_required_group.setExclusive(True)
        self.quality_report_yes_radio = QRadioButton("是")
        self.quality_report_no_radio = QRadioButton("否")
        self.quality_report_required_group.addButton(self.quality_report_yes_radio, 1)
        self.quality_report_required_group.addButton(self.quality_report_no_radio, 0)
        self.category_input = QComboBox()
        self.category_input.setEditable(False)
        self._populate_category_combo()
        if not self._is_edit and not self._initial_data and prefs.default_anomaly_category:
            set_combo_current_text(self.category_input, prefs.default_anomaly_category)

        # Long supplier/product labels must not dictate the dialog's minimum width.
        for combo in (self.supplier_combo, self.product_combo, self.category_input):
            combo.setMinimumWidth(0)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(12)

        self.problem_input = BulletListWidget(placeholder="輸入不良現象...")
        self.pending_items_input = BulletListWidget(placeholder="輸入確認事項 / 待追蹤...")
        self.process_keywords_input = TagInputWidget()

        # 2. 單一可捲動頁面；底部按鈕列由 apply_dialog_layout 固定在外層。
        self.form_scroll = QScrollArea()
        self.form_scroll.setObjectName("AnomalyFormScroll")
        self.form_scroll.setWidgetResizable(True)
        self.form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form_content = QWidget()
        form_content.setObjectName("AnomalyFormContent")
        content_layout = QVBoxLayout(form_content)
        content_layout.setContentsMargins(*DIALOG_OUTER_MARGINS)
        content_layout.setSpacing(FORM_VERTICAL_SPACING)

        basic_title = QLabel("📋 基本資訊")
        basic_title.setProperty("role", "sectionTitle")
        content_layout.addWidget(basic_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(GRID_GUTTER)
        grid.setVerticalSpacing(ROW_GAP)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        grid.addWidget(RequiredFieldLabel("供應商"), 0, 0)
        grid.addWidget(self.supplier_combo, 0, 1)
        grid.addWidget(RequiredFieldLabel("日期"), 0, 2)
        grid.addWidget(self.date_edit, 0, 3)

        product_row = QWidget()
        pr_layout = QHBoxLayout(product_row)
        pr_layout.setContentsMargins(0, 0, 0, 0)
        pr_layout.setSpacing(INLINE_SPACING)
        pr_layout.addWidget(self.product_combo, 3)
        pr_layout.addWidget(self.product_stage_combo, 1)

        grid.addWidget(RequiredFieldLabel("品名"), 1, 0)
        grid.addWidget(product_row, 1, 1)
        grid.addWidget(QLabel("料號"), 1, 2)
        grid.addWidget(self.product_code_input, 1, 3)

        self._product_guard_label = QLabel("")
        self._product_guard_label.setProperty("role", "messageText")
        self._product_guard_label.setVisible(False)
        grid.addWidget(self._product_guard_label, 2, 1, 1, 3)

        grid.addWidget(RequiredFieldLabel("異常來源"), 3, 0)
        grid.addWidget(self.anomaly_source_combo, 3, 1)

        grid.addWidget(QLabel("異常類別"), 4, 0)
        grid.addWidget(self.category_input, 4, 1)
        grid.addWidget(QLabel("責任人"), 4, 2)
        grid.addWidget(self.responsible_person_input, 4, 3)

        grid.addWidget(QLabel("異常單號"), 5, 0)
        grid.addWidget(self.anomaly_no_preview_input, 5, 1)
        grid.addWidget(QLabel("數量"), 5, 2)
        grid.addWidget(self.batch_qty_input, 5, 3)

        due_row = QWidget()
        dr_layout = QHBoxLayout(due_row)
        dr_layout.setContentsMargins(0, 0, 0, 0)
        dr_layout.setSpacing(INLINE_SPACING)
        dr_layout.addWidget(self.due_date_check)
        dr_layout.addWidget(self.due_date_edit, 1)

        quality_report_row = QWidget()
        quality_report_layout = QHBoxLayout(quality_report_row)
        quality_report_layout.setContentsMargins(0, 0, 0, 0)
        quality_report_layout.setSpacing(INLINE_SPACING)
        quality_report_layout.addWidget(self.quality_report_yes_radio)
        quality_report_layout.addWidget(self.quality_report_no_radio)
        quality_report_layout.addStretch(1)

        grid.addWidget(RequiredFieldLabel("品質異常單要求"), 6, 0)
        grid.addWidget(quality_report_row, 6, 1)
        grid.addWidget(QLabel("預計回覆日"), 6, 2)
        grid.addWidget(due_row, 6, 3)

        trace_row = 7
        for field in TRACE_FIELD_LABELS:
            grid.addWidget(self._trace_labels[field], trace_row, 0)
            grid.addWidget(self._trace_inputs[field], trace_row, 1, 1, 3)
            trace_row += 1
        self._lbl_order = self._trace_labels[TRACE_FIELD_OUTSOURCE_WORK_ORDER]

        content_layout.addLayout(grid)

        desc_title = QLabel("🔍 問題描述")
        desc_title.setProperty("role", "sectionTitle")
        content_layout.addWidget(desc_title)
        content_layout.addWidget(QLabel("SMT 製程關鍵詞"))
        content_layout.addWidget(self.process_keywords_input)
        content_layout.addWidget(RequiredFieldLabel("不良現象描述"))
        content_layout.addWidget(self.problem_input)
        content_layout.addWidget(QLabel("📌 確認事項 / 待追蹤"))
        content_layout.addWidget(self.pending_items_input)

        self._rc_group = QGroupBox("📊 風險控管調查")
        rc_layout = QGridLayout(self._rc_group)
        rc_layout.setContentsMargins(*GROUPBOX_CONTENT_MARGINS)
        rc_layout.setHorizontalSpacing(GRID_GUTTER)
        rc_layout.setVerticalSpacing(ROW_GAP)
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
        content_layout.addWidget(self._rc_group)

        photo_title = QLabel("📷 現場照片")
        photo_title.setProperty("role", "sectionTitle")
        content_layout.addWidget(photo_title)
        self.attachment_editor = AttachmentEditor(self)
        self.attachment_editor.set_preview_height(ANOMALY_ATTACHMENT_COMPACT_HEIGHT)
        content_layout.addWidget(self.attachment_editor)
        content_layout.addStretch(1)
        if self._page_mode:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(form_content)
            self.page_content = self
            self.save_button = None
            self._button_box = None
            self.form_scroll = None
        else:
            self.page_content = None
            self.form_scroll.setWidget(form_content)
            # 3. 按鈕與對話框佈局
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
            )
            self.save_button = style_dialog_buttons(buttons)
            self._button_box = buttons
            buttons.accepted.connect(self._on_submit)
            buttons.rejected.connect(self.reject)

            apply_dialog_layout(self, self.form_scroll, buttons)
            fit_dialog_to_available_screen(
                self,
                preferred_width=ANOMALY_DIALOG_PREFERRED_WIDTH,
                preferred_height=ANOMALY_DIALOG_PREFERRED_HEIGHT,
                maximum_width=FORM_MAX_WIDTH,
            )
            self.form_scroll.verticalScrollBar().setValue(0)
        self._update_anomaly_no_preview()
        self.product_stage_combo.currentTextChanged.connect(
            lambda _: self._update_trace_row_visibility()
        )
        self._update_trace_row_visibility()
        self._setup_tab_order()

    def _setup_tab_order(self) -> None:
        """Tab follows visual reading order across fields, lists and actions."""
        order = [
            self.supplier_combo,
            self.date_edit,
            self.product_combo,
            self.product_stage_combo,
            self.product_code_input,
            self.anomaly_source_combo,
            self.category_input,
            self.responsible_person_input,
            self.anomaly_no_preview_input,
            self.batch_qty_input,
            self.quality_report_yes_radio,
            self.quality_report_no_radio,
            self.due_date_check,
            self.due_date_edit,
            *self._trace_inputs.values(),
            self.process_keywords_input,
            self.problem_input,
            self.pending_items_input,
            self.rc_supplier_inv_combo,
            self.rc_supplier_wip_combo,
            self.rc_in_transit_combo,
            self.rc_internal_inv_combo,
            self.attachment_editor,
        ]
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

    def _populate_anomaly_source_combo(self, orphan: str = "") -> None:
        labels = all_source_labels()
        self.anomaly_source_combo.clear()
        self.anomaly_source_combo.addItem("")
        self.anomaly_source_combo.addItems(labels)
        self._ensure_combo_value(self.anomaly_source_combo, orphan)

    def _populate_category_combo(self, orphan: str = "") -> None:
        labels = all_category_labels()
        self.category_input.clear()
        self.category_input.addItem("")
        self.category_input.addItems(labels)
        self._ensure_combo_value(self.category_input, orphan)

    @staticmethod
    def _ensure_combo_value(combo: QComboBox, value: str) -> None:
        text = str(value or "").strip()
        if not text:
            combo.setCurrentIndex(0)
            return
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        combo.insertItem(1, text)
        combo.setCurrentIndex(1)

    def _combo_value_is_orphan(self, combo: QComboBox, value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        labels = [combo.itemText(index) for index in range(combo.count())]
        preset_labels = {label.casefold() for label in labels if label}
        return text.casefold() not in preset_labels

    def _update_trace_row_visibility(self) -> None:
        """Show trace-number rows based on anomaly source and legacy compatibility."""
        source = normalize_anomaly_source(self.anomaly_source_combo.currentText())
        visible = set(visible_trace_fields_for_source(source))
        if not source:
            visible = {
                field
                for field, widget in self._trace_inputs.items()
                if bool(widget.text().strip())
            }
        for field, label in self._trace_labels.items():
            show = field in visible
            label.setVisible(show)
            self._trace_inputs[field].setVisible(show)
            if field in visible and field in required_trace_fields_for_source(source):
                label.setText(f"{TRACE_FIELD_LABELS[field]} *")
            else:
                label.setText(TRACE_FIELD_LABELS[field])

    def _apply_read_only(self) -> None:
        """Disable all input widgets to prevent modification."""
        self.date_edit.setEnabled(False)
        self.supplier_combo.setEnabled(False)
        self.product_combo.setEnabled(False)
        self.product_stage_combo.setEnabled(False)
        self.outsource_work_order_input.setReadOnly(True)
        for line_edit in self._trace_inputs.values():
            line_edit.setReadOnly(True)
        self.batch_qty_input.setReadOnly(True)
        self.category_input.setEnabled(False)
        self.anomaly_source_combo.setEnabled(False)
        self.responsible_person_input.setReadOnly(True)
        self.due_date_check.setEnabled(False)
        self.due_date_edit.setEnabled(False)
        self.quality_report_yes_radio.setEnabled(False)
        self.quality_report_no_radio.setEnabled(False)
        self.problem_input.setReadOnly(True)
        self.pending_items_input.setReadOnly(True)
        self.process_keywords_input.set_read_only(True)
        self.anomaly_no_preview_input.setReadOnly(True)

        self.rc_supplier_inv_combo.setEnabled(False)
        self.rc_supplier_wip_combo.setEnabled(False)
        self.rc_in_transit_combo.setEnabled(False)
        self.rc_internal_inv_combo.setEnabled(False)

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
            self.anomaly_source_combo.currentTextChanged,
            self.product_stage_combo.currentTextChanged,
            *[widget.textChanged for widget in self._trace_inputs.values()],
            self.batch_qty_input.textChanged,
            self.responsible_person_input.textChanged,
            self.anomaly_no_preview_input.textChanged,
            self.due_date_check.toggled,
            self.due_date_edit.dateChanged,
            self.quality_report_required_group.buttonToggled,
            self.category_input.currentTextChanged,
            self.problem_input.valueChanged,
            self.pending_items_input.valueChanged,
            self.process_keywords_input.valueChanged,
            self.rc_supplier_inv_combo.currentTextChanged,
            self.rc_supplier_wip_combo.currentTextChanged,
            self.rc_in_transit_combo.currentTextChanged,
            self.rc_internal_inv_combo.currentTextChanged,
            self.attachment_editor.add_button.clicked,
            self.attachment_editor.remove_button.clicked,
        ])

    def _on_date_changed(self, _date: QDate | None = None) -> None:
        self._update_anomaly_no_preview()

    def _update_anomaly_no_preview(self, _date: QDate | None = None):
        anomaly_date = self.date_edit.date().toString("yyyy-MM-dd")
        if self._is_edit:
            original_date = str(self._initial_data.get("anomaly_date") or "").strip()
            if anomaly_date == original_date:
                self.anomaly_no_preview_input.setText(self._fixed_anomaly_no or "")
                return
        try:
            preview = _anomaly_service.preview_anomaly_no(anomaly_date)
        except Exception:
            logger.exception("preview_anomaly_no failed for date %s", anomaly_date)
            preview = ""
        self.anomaly_no_preview_input.setText(preview)

    def _on_supplier_changed_post(self, supplier_id: str, products: list[dict]) -> None:
        self._refresh_submit_state()

    def _on_product_changed_post(self) -> None:
        self._refresh_submit_state()

    def can_submit(self) -> bool:
        """Return the established page/dialog eligibility without duplicating it."""
        supplier_id = (self.supplier_combo.currentData() or "").strip()
        product_id = (self.product_combo.currentData() or "").strip()
        return bool(supplier_id and product_id)

    def _refresh_submit_state(self) -> None:
        supplier_id = (self.supplier_combo.currentData() or "").strip()
        product_id = (self.product_combo.currentData() or "").strip()
        has_products = self.product_combo.count() > 1
        message = ""
        tone = "info"
        if not supplier_id:
            message = "請先選擇供應商。"
        elif not has_products and not product_id:
            message = f"此供應商尚未建立產品，請先到「{NAV_LABEL_MASTER_SEMI_FINISHED}」新增產品。"
            tone = "warning"
        elif not product_id:
            message = "請選擇產品後再儲存。"
        self._product_guard_label.setText(message)
        set_tone(self._product_guard_label, tone)
        self._product_guard_label.setVisible(bool(message))
        if self.save_button is not None:
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
            self.product_code_input.setText(self._product_code_by_id.get(product_id, product_code))
        else:
            self.product_code_input.clear()
        self.product_stage_combo.setCurrentText(
            normalize_product_stage_ui(self._initial_data.get("product_stage"))
        )

        source_value = normalize_anomaly_source(
            self._initial_data.get("anomaly_source", self._initial_data.get("default_anomaly_source"))
        )
        if not source_value and self._initial_data.get("anomaly_source_hint"):
            source_value = normalize_anomaly_source(self._initial_data.get("anomaly_source_hint"))
        raw_source = str(
            self._initial_data.get("anomaly_source", self._initial_data.get("default_anomaly_source", ""))
            or ""
        ).strip()
        if not source_value and raw_source:
            source_value = raw_source
        self._populate_anomaly_source_combo(source_value)

        for field, widget in self._trace_inputs.items():
            widget.setText(str(self._initial_data.get(field) or ""))
        self.batch_qty_input.setText(str(self._initial_data.get("batch_qty") or ""))
        self.problem_input.set_formatted_text(str(self._initial_data.get("problem_desc") or ""))
        self.process_keywords_input.set_delimited_text(
            self._initial_data.get("process_keywords", "")
        )
        # 載入原始 category
        category_value = str(
            self._initial_data.get("category_raw", self._initial_data.get("category")) or ""
        )
        self._populate_category_combo(category_value)
        self.responsible_person_input.setText(
            str(self._initial_data.get("responsible_person") or "")
        )
        due_date_value = str(self._initial_data.get("due_date") or "").strip()
        if due_date_value:
            parsed_due = QDate.fromString(due_date_value, "yyyy-MM-dd")
            if parsed_due.isValid():
                self.due_date_check.setChecked(True)
                self.due_date_edit.setDate(parsed_due)
        self.pending_items_input.set_formatted_text(
            str(self._initial_data.get("pending_items") or "")
        )
        quality_report_required = self._initial_data.get("quality_report_required")
        if quality_report_required is not None:
            button = self.quality_report_required_group.button(
                1 if bool(quality_report_required) else 0
            )
            if button is not None:
                button.setChecked(True)
        self._update_trace_row_visibility()

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

        self._refresh_submit_state()
        if self._is_edit:
            self.attachment_editor.load_existing_attachments(self._anomaly_id)

    def _on_submit(self):
        quality_report_required_id = self.quality_report_required_group.checkedId()
        if quality_report_required_id not in (0, 1):
            QMessageBox.warning(self, "驗證失敗", "請選擇品質異常單要求：是或否。")
            return
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
        if not self.problem_input.get_formatted_text().strip():
            QMessageBox.warning(self, "驗證失敗", "不良現象描述為必填（請至少新增並填寫一條項目）")
            return
        anomaly_source = normalize_anomaly_source(self.anomaly_source_combo.currentText())
        raw_source = self.anomaly_source_combo.currentText().strip()
        if not anomaly_source and raw_source:
            QMessageBox.warning(
                self,
                "驗證失敗",
                "異常來源已不在辭庫中，請改選有效選項後再儲存。",
            )
            return
        if not anomaly_source and not self._is_edit:
            QMessageBox.warning(self, "驗證失敗", "請選擇異常來源")
            return
        category = self.category_input.currentText().strip()
        if category and not is_valid_category(category):
            QMessageBox.warning(
                self,
                "驗證失敗",
                "異常類別已不在辭庫中，請改選有效選項後再儲存。",
            )
            return
        payload = {
            "anomaly_no": anomaly_no_val,
            "anomaly_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "supplier_id": (self.supplier_combo.currentData() or "").strip(),
            "product_id": product_id,
            "problem_desc": self.problem_input.get_formatted_text(),
            "category": category,
            "process_keywords": self.process_keywords_input.get_delimited_text(),
            "anomaly_source": anomaly_source,
            **{
                field: self._trace_inputs[field].text().strip()
                for field in TRACE_FIELD_LABELS
            },
            "batch_qty": int(self.batch_qty_input.text().strip() or 0),
            "responsible_person": self.responsible_person_input.text().strip(),
            "due_date": due_date_value,
            "pending_items": self.pending_items_input.get_formatted_text(),
            "sync_visit": False,
            "rc_supplier_inventory": self.rc_supplier_inv_combo.currentText(),
            "rc_supplier_wip": self.rc_supplier_wip_combo.currentText(),
            "rc_in_transit": self.rc_in_transit_combo.currentText(),
            "rc_internal_inventory": self.rc_internal_inv_combo.currentText(),
            "quality_report_required": bool(quality_report_required_id),
            "source_defect_no": str(self._initial_data.get("source_defect_no") or ""),
        }
        try:
            if self._is_edit:
                result = _anomaly_service.update_anomaly(self._anomaly_id, payload)
                self.attachment_editor.save_to_anomaly(self._anomaly_id)
                self._warn_if_attachment_rename_failures()
                completion_text = "異常資料已更新"
            else:
                result = _anomaly_service.create_anomaly_with_visit_link(payload)
                anomaly_id = str(result.get("anomaly_id") or "").strip()
                if anomaly_id:
                    self.attachment_editor.save_to_anomaly(anomaly_id)
                    self._warn_if_attachment_rename_failures()
                completion_text = f"已建立異常單：{result['anomaly_no']}"
            warnings = (
                list(result.get("warnings") or [])
                if isinstance(result, dict)
                else list(getattr(result, "warnings", ()) or ())
            )
            if warnings:
                QMessageBox.warning(
                    self,
                    "完成但有警告",
                    localize_popup_message(
                        completion_text + "\n\n" + "\n".join(str(item) for item in warnings)
                    ),
                )
            else:
                QMessageBox.information(
                    self,
                    "成功",
                    localize_popup_message(completion_text),
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
