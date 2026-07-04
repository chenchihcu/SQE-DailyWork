from __future__ import annotations

import os
import sqlite3
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFrame

from ncr.db import crud
from ncr.db.database import apply_schema
from ncr.ui.defect_form import DefectEditDialog, DefectFieldsWidget, QuickProductCreateDialog


class NcrDefectFormProductSelectionTests(unittest.TestCase):
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
            """
            INSERT INTO product_records (item_no, product_name, created_at)
            VALUES (?, ?, ?)
            """,
            ("ITEM-001", "測試產品 A", "2026-06-03T09:00:00"),
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
                "product_name": "測試產品 A",
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
        widget = DefectFieldsWidget(self.conn)
        self.addCleanup(widget.deleteLater)

        index = widget.item_no_input.findText("ITEM-001")
        self.assertGreaterEqual(index, 0)

        widget.item_no_input.setCurrentIndex(index)
        self.app.processEvents()

        self.assertEqual("ITEM-001", widget.item_no_input.currentText())
        self.assertEqual("測試產品 A", widget.product_name_input.text())

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

    def test_quick_product_dialog_is_direct_form_without_section_card(self) -> None:
        dialog = QuickProductCreateDialog(self.conn, "ITEM-NEW")
        dialog.show()
        self.app.processEvents()
        self.addCleanup(dialog.close)

        section_cards = [
            frame
            for frame in dialog.findChildren(QFrame)
            if frame.property("uiRole") == "sectionCard"
        ]
        self.assertEqual([], section_cards)
        self.assertTrue(dialog.save_button.isVisible())
        self.assertTrue(dialog.cancel_button.isVisible())

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
