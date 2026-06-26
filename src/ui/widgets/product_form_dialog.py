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
    RequiredFieldLabel,
    mark_button_variant,
    make_paired_form_row,
    set_combo_current_data,
)

logger = logging.getLogger(__name__)


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
            make_paired_form_row(
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
        mark_button_variant(save_button, "primary")
        mark_button_variant(cancel_button, "secondary")
        if save_button:
            save_button.setText("儲存")
        if cancel_button:
            cancel_button.setText("取消")
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
