"""Defect-note table and product-section editor widgets for visit / anomaly forms."""

from __future__ import annotations

import logging

from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.product_stage import (
    PRODUCT_STAGE_MASS_PRODUCTION,
    PRODUCT_STAGE_OPTIONS,
    normalize_product_stage_ui,
)
from ui.layout_constants import INLINE_SPACING
from ui.widgets.common_widgets import (
    RequiredFieldLabel,
    make_paired_form_row as _make_paired_form_row,
    set_combo_current_data as _set_combo_current_data,
)
from ui.widgets.defect_form_widgets import (
    product_label,
    set_text_edit_visible_rows,
)

logger = logging.getLogger(__name__)


class DefectNoteTable(QTableWidget):
    HEADERS = ("缺失內容", "改善內容", "備註")

    def __init__(self, parent=None):
        super().__init__(0, len(self.HEADERS), parent)
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setMinimumHeight(150)

    def add_empty_note(self) -> None:
        row = self.rowCount()
        self.insertRow(row)
        for col in range(len(self.HEADERS)):
            self.setItem(row, col, QTableWidgetItem(""))
        self.setCurrentCell(row, 0)

    def remove_selected_note(self) -> None:
        row = self.currentRow()
        if row >= 0:
            self.removeRow(row)

    def load_notes(self, notes: list[dict]) -> None:
        self.setRowCount(0)
        for note in notes:
            row = self.rowCount()
            self.insertRow(row)
            values = (
                note.get("defect_desc", ""),
                note.get("improvement_desc", ""),
                note.get("note", ""),
            )
            for col, value in enumerate(values):
                self.setItem(row, col, QTableWidgetItem(str(value or "")))

    def notes(self) -> list[dict]:
        result: list[dict] = []
        for row in range(self.rowCount()):
            defect = self._cell_text(row, 0)
            improvement = self._cell_text(row, 1)
            note = self._cell_text(row, 2)
            if not any((defect, improvement, note)):
                continue
            if not defect:
                raise ValueError("缺失內容為必填")
            result.append(
                {
                    "defect_desc": defect,
                    "improvement_desc": improvement,
                    "note": note,
                    "sort_order": len(result),
                }
            )
        return result

    def _cell_text(self, row: int, col: int) -> str:
        item = self.item(row, col)
        return item.text().strip() if item is not None else ""


class ProductSectionEditor(QGroupBox):
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self._product_stage_by_id: dict[str, str] = {}
        self._product_code_by_id: dict[str, str] = {}
        self.product_combo = QComboBox()
        self.product_combo.currentIndexChanged.connect(self._on_product_changed)
        self.product_stage_combo = QComboBox()
        self.product_stage_combo.addItems(PRODUCT_STAGE_OPTIONS)
        self.product_stage_combo.setCurrentText(PRODUCT_STAGE_MASS_PRODUCTION)
        self.product_stage_combo.setEnabled(False)
        self.product_code_input = QLineEdit()
        self.product_code_input.setReadOnly(True)
        self.time_slot_input = QLineEdit()
        self.time_slot_input.setPlaceholderText("上午 / 下午 / 產線時段")
        self.work_order_input = QLineEdit()
        self.qty_input = QLineEdit()
        self.qty_input.setValidator(QIntValidator(0, 10_000_000))
        self.summary_input = QTextEdit()
        self.summary_input.setPlaceholderText("產品區段摘要（選填）")
        set_text_edit_visible_rows(self.summary_input, 3)
        self.defect_table = DefectNoteTable()
        add_note_button = QPushButton("新增缺失")
        add_note_button.setProperty("variant", "secondary")
        add_note_button.clicked.connect(self.defect_table.add_empty_note)
        remove_note_button = QPushButton("刪除缺失")
        remove_note_button.setProperty("tone", "warning")
        remove_note_button.clicked.connect(self.defect_table.remove_selected_note)

        form = QFormLayout()
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(INLINE_SPACING)
        row_layout.addWidget(self.product_combo, 3)
        row_layout.addWidget(self.product_stage_combo, 1)
        form.addRow(RequiredFieldLabel("品名"), row)
        form.addRow("料號", self.product_code_input)
        form.addRow(
            _make_paired_form_row(
                "ProductSectionTimeOrderRow",
                "時段",
                self.time_slot_input,
                "工單",
                self.work_order_input,
            )
        )
        form.addRow("數量", self.qty_input)
        form.addRow("摘要", self.summary_input)

        note_buttons = QHBoxLayout()
        note_buttons.addWidget(add_note_button)
        note_buttons.addWidget(remove_note_button)
        note_buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("缺失 / 改善紀錄"))
        layout.addWidget(self.defect_table)
        layout.addLayout(note_buttons)

    def set_products(self, products: list[dict]) -> None:
        current = (self.product_combo.currentData() or "").strip()
        self.product_combo.blockSignals(True)
        try:
            self.product_combo.clear()
            self.product_combo.addItem("請選擇產品", "")
            self._product_stage_by_id = {}
            self._product_code_by_id = {}
            for item in products:
                product_id = str(item.get("id") or "").strip()
                self.product_combo.addItem(product_label(item), product_id)
                if product_id:
                    self._product_stage_by_id[product_id] = normalize_product_stage_ui(
                        item.get("product_stage")
                    )
                    self._product_code_by_id[product_id] = str(item.get("product_code") or "").strip()
        finally:
            self.product_combo.blockSignals(False)
        if current:
            _set_combo_current_data(self.product_combo, current)
        self._on_product_changed()

    def load_data(self, section: dict) -> None:
        product_id = str(section.get("product_id") or "").strip()
        if product_id and not _set_combo_current_data(self.product_combo, product_id):
            self.product_combo.addItem(str(section.get("product_name") or product_id), product_id)
            self._product_stage_by_id[product_id] = normalize_product_stage_ui(
                section.get("product_stage")
            )
            self._product_code_by_id[product_id] = str(section.get("product_code") or "")
            _set_combo_current_data(self.product_combo, product_id)
        self.product_stage_combo.setCurrentText(
            normalize_product_stage_ui(section.get("product_stage"))
        )
        self.product_code_input.setText(str(section.get("product_code") or ""))
        self.time_slot_input.setText(str(section.get("time_slot") or ""))
        self.work_order_input.setText(str(section.get("work_order_no") or ""))
        qty = int(section.get("production_qty") or 0)
        self.qty_input.setText(str(qty) if qty else "")
        self.summary_input.setPlainText(str(section.get("summary") or ""))
        self.defect_table.load_notes(list(section.get("defect_notes") or []))

    def section_data(self) -> dict | None:
        product_id = (self.product_combo.currentData() or "").strip()
        notes = self.defect_table.notes()
        has_content = any(
            (
                product_id,
                self.time_slot_input.text().strip(),
                self.work_order_input.text().strip(),
                self.qty_input.text().strip(),
                self.summary_input.toPlainText().strip(),
                notes,
            )
        )
        if not has_content:
            return None
        if not product_id:
            raise ValueError("產品區段需選擇品名")
        return {
            "product_id": product_id,
            "product_name": self.product_combo.currentText().strip(),
            "product_stage": self.product_stage_combo.currentText(),
            "product_code": self.product_code_input.text().strip(),
            "time_slot": self.time_slot_input.text().strip(),
            "work_order_no": self.work_order_input.text().strip(),
            "production_qty": int(self.qty_input.text().strip() or 0),
            "summary": self.summary_input.toPlainText().strip(),
            "defect_notes": notes,
        }

    def set_read_only(self) -> None:
        for widget in (
            self.product_combo,
            self.product_stage_combo,
            self.time_slot_input,
            self.work_order_input,
            self.qty_input,
        ):
            widget.setEnabled(False)
        self.product_code_input.setReadOnly(True)
        self.summary_input.setReadOnly(True)
        self.defect_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    def _on_product_changed(self, _index: int = -1) -> None:
        product_id = (self.product_combo.currentData() or "").strip()
        self.product_stage_combo.setCurrentText(
            self._product_stage_by_id.get(product_id, PRODUCT_STAGE_MASS_PRODUCTION)
        )
        self.product_code_input.setText(self._product_code_by_id.get(product_id, ""))
