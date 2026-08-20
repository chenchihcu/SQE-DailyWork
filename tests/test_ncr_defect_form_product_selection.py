from __future__ import annotations

import os
import sqlite3
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QFrame

from ncr.db import crud
from ncr.db.database import apply_schema
from ncr.ui.defect_form import DefectEditDialog, DefectFieldsWidget


class NcrDefectFormProductSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            pass  # do not terminate shared QApplication singleton in test runner

    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        apply_schema(self.conn, with_version=True)
        self.conn.execute(
            "INSERT INTO product_records (item_no, product_name, created_at) VALUES (?, ?, ?)",
            ("ITEM-001", "Testing Product A", "2026-06-03T09:00:00"),
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def _insert_defect_record(self) -> int:
        return crud.insert_defect(
            self.conn,
            {
                "defect_no": "D-TEST-001",
                "event_date": "2026-06-04",
                "processing_line": "原物料",
                "return_slip_type": "廠內退料",
                "work_order_no": "WO-001",
                "internal_work_order_no": "",
                "transfer_slip_no": "",
                "item_no": "ITEM-001",
                "product_name": "Testing Product A",
                "qty": 1,
                "category": "原物料",
                "supplier_name": "測試供應商",
                "outsource_supplier_name": "",
                "defect_desc": "測試不良描述",
                "status": "處理中",
                "disposition": "重工",
                "responsibility": "材損",
                "created_at": "2026-06-04T09:00:00",
            },
        )

    def test_selecting_database_item_number_populates_product_name(self) -> None:
        # New behavior: without a supplier selected, item list is empty (strict mode).
        # NCR test env uses standalone product_records TABLE (not a VIEW), so
        # get_products_by_supplier_name safely returns [] -> no items in dropdown.
        # Verify 1: no supplier -> ITEM-001 not in dropdown
        # Verify 2: manual text entry still populates product name via sync_product_name_from_item_no
        widget = DefectFieldsWidget(self.conn)
        self.addCleanup(widget.deleteLater)

        index = widget.item_no_input.findText("ITEM-001")
        self.assertEqual(-1, index, "No supplier: item list must be empty")

        widget.item_no_input.setCurrentText("ITEM-001")
        self.app.processEvents()

        self.assertEqual("ITEM-001", widget.item_no_input.currentText())
        self.assertEqual("Testing Product A", widget.product_name_input.text())

    def test_defect_fields_description_uses_full_width_without_placeholder(self) -> None:
        widget = DefectFieldsWidget(self.conn)
        self.addCleanup(widget.deleteLater)

        self.assertIsNone(widget.findChild(QFrame, "defectDescPlaceholder"))
        layout = widget.layout()
        self.assertIsNotNone(layout)
        assert layout is not None
        direct_widgets = [
            layout.itemAt(index).widget()
            for index in range(layout.count())
            if layout.itemAt(index).widget() is not None
        ]
        self.assertIn(widget.defect_desc_input, direct_widgets)

    @patch(
        "ncr.ui.defect_form.event_service.list_active_suppliers",
        return_value=[
            {"id": "supplier-1", "supplier_name": "測試供應商", "is_active": True}
        ],
    )
    @patch("ncr.ui.defect_form.event_service.create_product")
    @patch("ncr.ui.defect_form.ProductFormDialog")
    def test_product_master_button_uses_shared_product_form(
        self,
        dialog_type: Mock,
        create_product: Mock,
        _list_suppliers: Mock,
    ) -> None:
        fields = DefectFieldsWidget(self.conn)
        self.addCleanup(fields.deleteLater)
        fields.supplier_combo.lineEdit().setText("測試供應商")
        fields.item_no_input.lineEdit().setText("ITEM-NEW")
        dialog_type.return_value.exec.return_value = QDialog.DialogCode.Accepted
        dialog_type.return_value.payload.return_value = {
            "product_code": "ITEM-NEW",
            "product_name": "新產品",
            "product_stage": "量產",
            "supplier_id": "supplier-1",
            "secondary_supplier_id": "",
        }

        self.assertTrue(fields.open_product_master_dialog())

        dialog_type.assert_called_once()
        self.assertEqual(
            "ITEM-NEW",
            dialog_type.call_args.kwargs["initial_data"]["product_code"],
        )
        create_product.assert_called_once_with(
            dialog_type.return_value.payload.return_value
        )
        self.assertEqual("新產品", fields.product_name_input.text())

    def test_defect_edit_dialog_keeps_bottom_actions_visible(self) -> None:
        defect_id = self._insert_defect_record()
        dialog = DefectEditDialog(self.conn, defect_id)
        dialog.show()
        self.app.processEvents()
        self.addCleanup(dialog.close)

        self.assertTrue(dialog.save_button.isVisible())
        self.assertTrue(dialog.cancel_button.isVisible())
        self.assertTrue(dialog.info_label.isVisible())


if __name__ == "__main__":
    unittest.main()
