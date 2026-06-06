from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QTextEdit, QWidget

from database.connection import initialize_database
from ui.layout_constants import FORM_MAX_WIDTH
from ui.widgets.defect_form_widget import (
    CloseAnomalyDialog,
    NewAnomalyDialog,
    NewVisitDialog,
    ProductSectionEditor,
)
from ui.widgets.master_data_widget import ProductFormDialog, SupplierFormDialog


class FormFieldPairingLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        initialize_database()
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        self.app.processEvents()

    def _show_dialog(self, dialog: QDialog) -> QDialog:
        dialog.show()
        self.app.processEvents()
        self.addCleanup(dialog.close)
        self.assertLessEqual(dialog.width(), FORM_MAX_WIDTH)
        self.assertLessEqual(dialog.minimumWidth(), FORM_MAX_WIDTH)
        button_box = dialog.findChild(QDialogButtonBox)
        self.assertIsNotNone(button_box)
        assert button_box is not None
        self.assertTrue(button_box.isVisible())
        bottom = button_box.mapTo(dialog, button_box.rect().bottomRight()).y()
        self.assertLessEqual(bottom, dialog.height())
        return dialog

    def _row(self, parent: QWidget, object_name: str) -> QWidget:
        row = parent.findChild(QWidget, object_name)
        self.assertIsNotNone(row, object_name)
        assert row is not None
        return row

    def _assert_row_contains(self, row: QWidget, *widgets: QWidget) -> None:
        for widget in widgets:
            self.assertTrue(row.isAncestorOf(widget), widget.objectName() or repr(widget))

    def _assert_compacted_text_edit(self, editor: QTextEdit, legacy_height: int) -> None:
        self.assertLess(editor.maximumHeight(), legacy_height)
        self.assertEqual(editor.minimumHeight(), editor.maximumHeight())

    def test_anomaly_dialog_compacts_long_text_fields_without_new_pairs(self) -> None:
        dialog = self._show_dialog(NewAnomalyDialog())

        self._assert_compacted_text_edit(dialog.problem_input, 180)
        self._assert_compacted_text_edit(dialog.pending_items_input, 100)
        paired_rows = [
            row
            for row in dialog.findChildren(QWidget)
            if row.objectName().endswith("Row")
        ]
        for row in paired_rows:
            self.assertFalse(row.isAncestorOf(dialog.supplier_combo))
            self.assertFalse(row.isAncestorOf(dialog.product_combo))

    def test_visit_dialog_pairs_only_good_candidate_fields(self) -> None:
        dialog = self._show_dialog(NewVisitDialog())

        basic_row = self._row(dialog, "VisitBasicDateVisitorRow")
        self._assert_row_contains(basic_row, dialog.date_edit, dialog.visitor_input)
        self.assertFalse(basic_row.isAncestorOf(dialog.supplier_combo))
        self.assertFalse(basic_row.isAncestorOf(dialog.product_combo))
        self.assertFalse(basic_row.isAncestorOf(dialog.product_code_input))

        time_order_row = self._row(dialog, "VisitAdvancedTimeOrderRow")
        self._assert_row_contains(
            time_order_row,
            dialog.time_slot_input,
            dialog.work_order_input,
        )

        qty_transfer_row = self._row(dialog, "VisitAdvancedQtyTransferRow")
        self._assert_row_contains(
            qty_transfer_row,
            dialog.qty_input,
            dialog.tech_transfer_check,
        )
        self._assert_compacted_text_edit(dialog.summary_input, 200)

    def test_product_section_pairs_time_and_work_order_only(self) -> None:
        editor = ProductSectionEditor("產品區段")
        self.addCleanup(editor.close)
        row = self._row(editor, "ProductSectionTimeOrderRow")
        self._assert_row_contains(row, editor.time_slot_input, editor.work_order_input)
        self.assertFalse(row.isAncestorOf(editor.product_combo))
        self.assertFalse(row.isAncestorOf(editor.product_code_input))
        self.assertFalse(row.isAncestorOf(editor.qty_input))
        self.assertEqual(editor.summary_input.minimumHeight(), editor.summary_input.maximumHeight())
        self.assertLessEqual(editor.summary_input.maximumHeight(), 80)

    def test_close_anomaly_pairs_close_owner_and_cause(self) -> None:
        dialog = self._show_dialog(CloseAnomalyDialog("missing-id", "測試問題描述"))

        row = self._row(dialog, "CloseAnomalyCloserCauseRow")
        self._assert_row_contains(row, dialog.closer_input, dialog.root_cause_combo)
        self.assertFalse(row.isAncestorOf(dialog.improvement_input))
        self.assertFalse(row.isAncestorOf(dialog.attachment_editor))

    def test_supplier_dialog_pairs_contact_fields(self) -> None:
        dialog = self._show_dialog(SupplierFormDialog())
        contact_row = self._row(dialog, "SupplierContactDeptRow")
        self._assert_row_contains(
            contact_row,
            dialog.contact_name_input,
            dialog.department_input,
        )
        phone_row = self._row(dialog, "SupplierPhoneEmailRow")
        self._assert_row_contains(
            phone_row,
            dialog.phone_input,
            dialog.contact_email_input,
        )
        self.assertFalse(contact_row.isAncestorOf(dialog.supplier_name_input))
        self.assertFalse(phone_row.isAncestorOf(dialog.supplier_name_input))

    def test_product_dialog_pairs_code_and_stage_only(self) -> None:
        dialog = self._show_dialog(
            ProductFormDialog([{"id": "supplier-1", "supplier_name": "測試供應商"}])
        )
        row = self._row(dialog, "ProductCodeStageRow")
        self._assert_row_contains(
            row,
            dialog.product_code_input,
            dialog.product_stage_combo,
        )
        self.assertFalse(row.isAncestorOf(dialog.product_name_input))
        self.assertFalse(row.isAncestorOf(dialog.primary_supplier_combo))
        self.assertFalse(row.isAncestorOf(dialog.secondary_supplier_combo))


if __name__ == "__main__":
    unittest.main()
