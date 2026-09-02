from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from database.product_item_category import (
    ITEM_CATEGORY_FINISHED,
    ITEM_CATEGORY_RAW_MATERIAL,
    ITEM_CATEGORY_SEMI_FINISHED,
    infer_item_category_from_product_code,
    normalize_item_category,
)
from database.product_stage import (
    PRODUCT_STAGE_MASS_PRODUCTION,
    PRODUCT_STAGE_OPTIONS,
    PRODUCT_STAGE_TRIAL_PRODUCTION,
    normalize_product_stage_ui,
)
from ui.layout_constants import (
    DIALOG_OUTER_MARGINS,
    FORM_HORIZONTAL_SPACING,
    FORM_VERTICAL_SPACING,
    FORM_MAX_WIDTH,
)
from ui.popup_i18n import localize_popup_message
from ui.window_sizing import fit_dialog_to_available_screen
from ui.widgets.common_widgets import (
    DirtyTrackingMixin,
    RequiredFieldLabel,
    make_inline_error_label,
    mark_button_variant,
    make_paired_form_row,
    set_combo_current_data,
    set_field_invalid,
)

logger = logging.getLogger(__name__)


class ProductFormDialog(DirtyTrackingMixin, QDialog):
    def __init__(
        self,
        suppliers: list[dict],
        parent=None,
        *,
        initial_data: dict | None = None,
        is_edit: bool = False,
        fixed_item_category: str | None = None,
        allow_item_category_choice: bool = False,
    ):
        super().__init__(parent)
        self._suppliers = suppliers
        self._initial_data = initial_data or {}
        self._is_edit = is_edit
        self._fixed_item_category = (fixed_item_category or "").strip() or None
        self._allow_item_category_choice = allow_item_category_choice
        self._stage_change_reason = ""
        self.setModal(True)
        self.setWindowTitle("編輯產品" if self._is_edit else "新增產品")
        self.setMinimumWidth(560)
        self.setMaximumWidth(FORM_MAX_WIDTH)
        self._setup_ui()
        self._apply_initial_data()
        change_signals = [
            self.product_code_input.textChanged,
            self.product_name_input.textChanged,
            self.product_stage_combo.currentTextChanged,
            self.primary_supplier_combo.currentIndexChanged,
            self.secondary_supplier_combo.currentIndexChanged,
        ]
        if self._fixed_item_category or self._allow_item_category_choice:
            change_signals.append(self.item_category_combo.currentTextChanged)
        self._init_dirty_tracking(change_signals)
        # Clear field-level errors in real time as soon as the user edits.
        for signal in change_signals:
            signal.connect(self._clear_validation)
        self.product_code_input.textChanged.connect(self._on_product_code_changed)
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
        self.product_code_input.setAccessibleName("料號")
        self.product_name_input = QLineEdit()
        self.product_name_input.setPlaceholderText("輸入品名")
        self.product_name_input.setAccessibleName("品名")

        self.product_stage_combo = QComboBox()
        self.product_stage_combo.addItems(list(PRODUCT_STAGE_OPTIONS))
        self.product_stage_combo.setCurrentText(PRODUCT_STAGE_MASS_PRODUCTION)
        self.product_stage_combo.setAccessibleName("產品階段")

        self.item_category_combo = QComboBox()
        self.item_category_combo.setAccessibleName("品項類別")

        self.primary_supplier_combo = QComboBox()
        self.primary_supplier_combo.setAccessibleName("主供應商")
        self.secondary_supplier_combo = QComboBox()
        self.secondary_supplier_combo.setAccessibleName("次供應商")
        self._load_supplier_options()

        form.addRow(
            make_paired_form_row(
                "ProductCodeStageRow",
                RequiredFieldLabel("料號"),
                self.product_code_input,
                "階段",
                self.product_stage_combo,
            )
        )
        form.addRow(RequiredFieldLabel("品名"), self.product_name_input)
        if self._fixed_item_category or self._allow_item_category_choice:
            if self._allow_item_category_choice:
                self.item_category_combo.addItems(
                    [ITEM_CATEGORY_SEMI_FINISHED, ITEM_CATEGORY_FINISHED]
                )
                form.addRow("品項類別", self.item_category_combo)
            else:
                self.item_category_combo.addItem(self._fixed_item_category or "")
                self.item_category_combo.setEnabled(False)
                form.addRow("品項類別", self.item_category_combo)
        form.addRow(
            make_paired_form_row(
                "ProductSuppliersRow",
                RequiredFieldLabel("主供應商"),
                self.primary_supplier_combo,
                "次要供應商",
                self.secondary_supplier_combo,
            )
        )
        layout.addLayout(form)

        self.inline_error = make_inline_error_label()
        layout.addWidget(self.inline_error)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        mark_button_variant(save_button, "primary")
        mark_button_variant(cancel_button, "secondary")
        if save_button:
            save_button.setText("儲存")
            save_button.setCursor(Qt.PointingHandCursor)
            save_button.setAccessibleName("儲存產品")
        if cancel_button:
            cancel_button.setText("取消")
            cancel_button.setCursor(Qt.PointingHandCursor)
            cancel_button.setAccessibleName("取消儲存")
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_supplier_options(self) -> None:
        self.primary_supplier_combo.clear()
        self.primary_supplier_combo.addItem("請選擇主供應商", "")

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
        if self._fixed_item_category or self._allow_item_category_choice:
            initial_category = normalize_item_category(
                self._initial_data.get("item_category")
                or self._fixed_item_category
                or ITEM_CATEGORY_SEMI_FINISHED
            )
            self.item_category_combo.setCurrentText(initial_category)

        supplier_id = str(self._initial_data.get("supplier_id") or "").strip()
        if supplier_id and not set_combo_current_data(self.primary_supplier_combo, supplier_id):
            self.primary_supplier_combo.addItem(f"{supplier_id}（目前值）", supplier_id)
            set_combo_current_data(self.primary_supplier_combo, supplier_id)

        secondary_supplier_id = str(
            self._initial_data.get("secondary_supplier_id") or ""
        ).strip()
        if secondary_supplier_id and not set_combo_current_data(
            self.secondary_supplier_combo, secondary_supplier_id
        ):
            self.secondary_supplier_combo.addItem(
                f"{secondary_supplier_id}（目前值）", secondary_supplier_id
            )
            set_combo_current_data(self.secondary_supplier_combo, secondary_supplier_id)
        self._on_product_code_changed(self.product_code_input.text())

    def _on_product_code_changed(self, _text: str = "") -> None:
        if not (self._fixed_item_category or self._allow_item_category_choice):
            return
        product_code = self.product_code_input.text().strip()
        current = normalize_item_category(self.item_category_combo.currentText())
        inferred = infer_item_category_from_product_code(product_code, current=current)
        if self._allow_item_category_choice:
            self.item_category_combo.setCurrentText(inferred)
        warning = ""
        if self._fixed_item_category == ITEM_CATEGORY_RAW_MATERIAL and product_code:
            if not product_code.startswith("0"):
                warning = "料號編碼原則：0 開頭為原物料；此料號建議於「原物料」主檔頁維護。"
        elif self._allow_item_category_choice and product_code.startswith("0"):
            warning = "料號編碼原則：0 開頭為原物料；建議改至「原物料」主檔頁維護。"
        if warning:
            self.inline_error.setText(warning)
            self.inline_error.setVisible(True)
        elif not self.inline_error.text().startswith("料號為必填"):
            self.inline_error.setVisible(False)

    def _on_submit(self) -> None:
        product_code = self.product_code_input.text().strip()
        product_name = self.product_name_input.text().strip()
        supplier_id = str(self.primary_supplier_combo.currentData() or "").strip()
        secondary_supplier_id = str(
            self.secondary_supplier_combo.currentData() or ""
        ).strip()

        errors: list[tuple] = []
        if not product_code:
            errors.append((self.product_code_input, "料號為必填，請輸入料號"))
        if not product_name:
            errors.append((self.product_name_input, "產品名稱為必填，請輸入品名"))
        if not supplier_id:
            errors.append((self.primary_supplier_combo, "請選擇主供應商"))
        if secondary_supplier_id and secondary_supplier_id == supplier_id:
            errors.append(
                (self.secondary_supplier_combo, "2nd source 不可與主供應商相同，請改選")
            )
        if errors:
            self._show_validation_errors(errors)
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

        self._dirty = False
        self.accept()

    def _clear_validation(self, *args) -> None:
        for field in (
            self.product_code_input,
            self.product_name_input,
            self.primary_supplier_combo,
            self.secondary_supplier_combo,
        ):
            set_field_invalid(field, False)
        self.inline_error.setVisible(False)

    def _show_validation_errors(self, errors) -> None:
        for field, _ in errors:
            set_field_invalid(field, True)
        first_field, first_msg = errors[0]
        text = first_msg if len(errors) == 1 else f"{first_msg}（共 {len(errors)} 項待修正）"
        self.inline_error.setText(text)
        self.inline_error.setVisible(True)
        first_field.setFocus()

    def payload(self) -> dict:
        product_code = self.product_code_input.text().strip()
        if self._fixed_item_category or self._allow_item_category_choice:
            current = normalize_item_category(self.item_category_combo.currentText())
            item_category = infer_item_category_from_product_code(
                product_code,
                current=current,
            )
        else:
            item_category = ITEM_CATEGORY_SEMI_FINISHED
        return {
            "product_code": product_code,
            "product_name": self.product_name_input.text().strip(),
            "product_stage": normalize_product_stage_ui(
                self.product_stage_combo.currentText()
            ),
            "item_category": item_category,
            "supplier_id": str(self.primary_supplier_combo.currentData() or "").strip(),
            "secondary_supplier_id": str(
                self.secondary_supplier_combo.currentData() or ""
            ).strip(),
            "stage_change_reason": self._stage_change_reason,
        }
