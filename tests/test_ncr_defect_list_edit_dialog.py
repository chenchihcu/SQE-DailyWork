from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3

from PySide6.QtWidgets import QApplication

from ncr.db import crud, database
from ncr.services import defect_service
from ncr.ui.defect_list import DefectListWidget


class DefectListEditDialogTests(unittest.TestCase):
    """Regression test for audit finding A11: opening the edit dialog for a
    row that vanished between the list refresh and the click (e.g. deleted
    from another window) must not let a raw ValueError propagate out of
    open_edit_dialog."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

    def _create_memory_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        database.apply_schema(conn, with_version=True)
        return conn

    def setUp(self) -> None:
        self.conn = self._create_memory_connection()
        payload = {
            "event_date": "2026-04-14",
            "processing_line": "原物料",
            "return_slip_type": "廠內退料",
            "work_order_no": "5102-260414001",
            "item_no": "ITEM-1001",
            "product_name": "Motor",
            "qty": 5,
            "category": "成品",
            "supplier_name": "A Supplier",
            "outsource_supplier_name": "Outsource A",
            "defect_desc": "Scratch on housing",
            "status": "處理中",
            "disposition": "重工",
        }
        defect_no = defect_service.create_defect(self.conn, payload)
        row = self.conn.execute(
            "SELECT id FROM defect_records WHERE defect_no = ?", (defect_no,)
        ).fetchone()
        self.defect_id = int(row["id"])
        self.widget = DefectListWidget(self.conn, workflow="tracking")

    def tearDown(self) -> None:
        self.widget.close()
        self.conn.close()

    def test_open_edit_dialog_recovers_when_record_already_deleted(self) -> None:
        self.assertGreaterEqual(len(self.widget.open_results), 1)

        # Simulate another window deleting the record after this widget's
        # last refresh, so its cached open_results still references the
        # now-gone id.
        crud.delete_defect(self.conn, self.defect_id)

        with patch("ncr.ui.defect_list.QMessageBox.warning") as mock_warning:
            try:
                self.widget.open_edit_dialog(0, 0)
            except ValueError:
                self.fail(
                    "open_edit_dialog must catch ValueError from a "
                    "vanished record, not let it propagate"
                )
            mock_warning.assert_called_once()

        # refresh_data() must have run and dropped the now-deleted row.
        self.assertEqual(0, len(self.widget.open_results))


if __name__ == "__main__":
    unittest.main()
