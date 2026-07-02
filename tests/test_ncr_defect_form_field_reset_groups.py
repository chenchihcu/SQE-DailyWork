from __future__ import annotations

import os
import sqlite3
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication

from ncr.db.database import apply_schema
from ncr.models.defect import CATEGORY_OPTIONS, STATUS_OPTIONS
from ncr.models.labels import (
    LABEL_ITEM_NO,
    VALIDATION_ITEM_NO_NOT_FOUND,
    VALIDATION_REQUIRED,
)
from ncr.ui.defect_form import DefectFieldsWidget, DefectFormWidget


class DefectFormFieldResetGroupsTests(unittest.TestCase):
    """Covers audit findings A3/D4: reset_fields, prepare_next_continuous_entry,
    and _clear_form_internal must share one field-group definition, and the
    "清除" button (_clear_form_internal) must actually clear every field it
    claims to via its tooltip, including the fields it previously missed
    (event_date_edit, category_combo, qty_spin, status_combo,
    responsibility_combo)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        apply_schema(self.conn, with_version=True)

    def tearDown(self) -> None:
        self.conn.close()

    def _fill_all_fields(self, fields: DefectFieldsWidget) -> None:
        fields.event_date_edit.setDate(QDate(2020, 1, 1))
        fields.return_slip_type_combo.setCurrentIndex(
            min(1, fields.return_slip_type_combo.count() - 1)
        )
        fields.work_order_input.setText("WO-CUSTOM")
        fields.internal_work_order_input.setText("IWO-CUSTOM")
        fields.transfer_slip_input.setText("TS-CUSTOM")
        fields.category_combo.setCurrentIndex(
            min(1, fields.category_combo.count() - 1)
        )
        fields.item_no_input.setCurrentText("ITEM-CUSTOM")
        fields.product_name_input.setText("Custom Product")
        fields.quick_add_product_btn.show()
        fields.qty_spin.setValue(9)
        fields.supplier_combo.setCurrentText("Custom Supplier")
        fields.defect_desc_input.setPlainText("Custom description")
        fields.status_combo.setCurrentText(STATUS_OPTIONS[-1])
        fields.disposition_combo.setCurrentIndex(
            min(1, fields.disposition_combo.count() - 1)
        )
        fields.responsibility_combo.setCurrentIndex(
            min(1, fields.responsibility_combo.count() - 1)
        )

    def test_reset_fields_clears_all_groups(self) -> None:
        widget = DefectFieldsWidget(self.conn)
        self.addCleanup(widget.deleteLater)
        self._fill_all_fields(widget)

        widget.reset_fields()

        self.assertEqual(QDate.currentDate(), widget.event_date_edit.date())
        self.assertEqual(0, widget.return_slip_type_combo.currentIndex())
        self.assertEqual("", widget.work_order_input.text())
        self.assertEqual("", widget.internal_work_order_input.text())
        self.assertEqual("", widget.transfer_slip_input.text())
        self.assertEqual(0, widget.category_combo.currentIndex())
        self.assertEqual("", widget.item_no_input.currentText())
        self.assertEqual("", widget.product_name_input.text())
        self.assertFalse(widget.quick_add_product_btn.isVisible())
        self.assertEqual(1, widget.qty_spin.value())
        self.assertEqual("", widget.supplier_combo.currentText())
        self.assertEqual(-1, widget.outsource_supplier_combo.currentIndex())
        self.assertEqual("", widget.defect_desc_input.toPlainText())
        self.assertEqual(STATUS_OPTIONS[0], widget.status_combo.currentText())
        self.assertEqual(0, widget.disposition_combo.currentIndex())
        self.assertEqual(0, widget.responsibility_combo.currentIndex())

    def test_prepare_next_continuous_entry_preserves_supplier_and_date(self) -> None:
        widget = DefectFieldsWidget(self.conn)
        self.addCleanup(widget.deleteLater)
        self._fill_all_fields(widget)

        preserved_date = widget.event_date_edit.date()
        preserved_return_slip_index = widget.return_slip_type_combo.currentIndex()
        preserved_work_order = widget.work_order_input.text()
        preserved_internal_work_order = widget.internal_work_order_input.text()
        preserved_category_index = widget.category_combo.currentIndex()
        preserved_supplier = widget.supplier_combo.currentText()

        widget.prepare_next_continuous_entry()

        # Preserved for consecutive same-batch entry.
        self.assertEqual(preserved_date, widget.event_date_edit.date())
        self.assertEqual(preserved_return_slip_index, widget.return_slip_type_combo.currentIndex())
        self.assertEqual(preserved_work_order, widget.work_order_input.text())
        self.assertEqual(preserved_internal_work_order, widget.internal_work_order_input.text())
        self.assertEqual(preserved_category_index, widget.category_combo.currentIndex())
        self.assertEqual(preserved_supplier, widget.supplier_combo.currentText())

        # Cleared for the next entry.
        self.assertEqual("", widget.transfer_slip_input.text())
        self.assertEqual("", widget.item_no_input.currentText())
        self.assertEqual("", widget.product_name_input.text())
        self.assertEqual(1, widget.qty_spin.value())
        self.assertEqual("", widget.defect_desc_input.toPlainText())
        self.assertEqual(STATUS_OPTIONS[0], widget.status_combo.currentText())
        self.assertEqual(0, widget.disposition_combo.currentIndex())
        self.assertEqual(0, widget.responsibility_combo.currentIndex())

    def test_clear_form_internal_matches_tooltip_promise(self) -> None:
        widget = DefectFormWidget(self.conn)
        self.addCleanup(widget.deleteLater)
        self._fill_all_fields(widget.fields_widget)

        widget._clear_form_internal()

        fields = widget.fields_widget
        self.assertEqual(QDate.currentDate(), fields.event_date_edit.date())
        self.assertEqual(0, fields.category_combo.currentIndex())
        self.assertEqual(1, fields.qty_spin.value())
        self.assertEqual(STATUS_OPTIONS[0], fields.status_combo.currentText())
        self.assertEqual(0, fields.responsibility_combo.currentIndex())
        self.assertEqual(0, fields.return_slip_type_combo.currentIndex())
        self.assertEqual("", fields.work_order_input.text())
        self.assertEqual("", fields.internal_work_order_input.text())
        self.assertEqual("", fields.transfer_slip_input.text())
        self.assertEqual("", fields.item_no_input.currentText())
        self.assertEqual("", fields.product_name_input.text())
        self.assertFalse(fields.quick_add_product_btn.isVisible())
        self.assertEqual("", fields.supplier_combo.currentText())
        self.assertEqual(-1, fields.outsource_supplier_combo.currentIndex())
        self.assertEqual("", fields.defect_desc_input.toPlainText())
        self.assertEqual(0, fields.disposition_combo.currentIndex())


class DefectFormItemNoRequiredTests(unittest.TestCase):
    """Covers audit finding A10 (user decision: item_no is required): the
    UI pre-check must reject blank item_no with the required-field message
    instead of deferring it to the service layer's generic ValueError path,
    matching the field's red required marker."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        apply_schema(self.conn, with_version=True)
        self.conn.execute(
            "INSERT INTO product_records (item_no, product_name, created_at) "
            "VALUES ('ITEM-KNOWN', '已知產品', '2026-06-01T09:00:00')"
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_blank_item_no_is_rejected_with_required_message(self) -> None:
        fields = DefectFieldsWidget(self.conn)
        self.addCleanup(fields.deleteLater)
        fields.item_no_input.setCurrentText("")
        self.assertEqual(
            VALIDATION_REQUIRED.format(LABEL_ITEM_NO),
            fields.item_no_validation_error(),
        )

    def test_unknown_item_no_keeps_not_found_message(self) -> None:
        fields = DefectFieldsWidget(self.conn)
        self.addCleanup(fields.deleteLater)
        fields.item_no_input.setCurrentText("ITEM-UNKNOWN")
        self.assertEqual(
            VALIDATION_ITEM_NO_NOT_FOUND,
            fields.item_no_validation_error(),
        )

    def test_known_item_no_passes(self) -> None:
        fields = DefectFieldsWidget(self.conn)
        self.addCleanup(fields.deleteLater)
        fields.item_no_input.setCurrentText("ITEM-KNOWN")
        self.assertIsNone(fields.item_no_validation_error())

    def test_save_record_blocks_blank_item_no(self) -> None:
        widget = DefectFormWidget(self.conn)
        self.addCleanup(widget.deleteLater)
        widget.show_popups = False
        widget.fields_widget.item_no_input.setCurrentText("")
        self.assertFalse(widget.save_record())


if __name__ == "__main__":
    unittest.main()
