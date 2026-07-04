from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sqlite3
from datetime import datetime

from PySide6.QtWidgets import QApplication

from ncr.db import crud, database
from ncr.models.defect import (
    PROCESSING_LINE_MATERIAL,
    PROCESSING_LINE_OUTSOURCE,
    PROCESSING_LINE_UNCLASSIFIED,
)
from ncr.services import defect_service
from ncr.ui.defect_list import DefectListWidget


def _insert_unclassified(conn: sqlite3.Connection, defect_no: str) -> None:
    """Insert a migrated-style 未分流 open record directly (bypassing form
    validation, which forbids 未分流) to mimic legacy/import data."""
    crud.insert_defect(
        conn,
        {
            "defect_no": defect_no,
            "event_date": "2026-03-01",
            "processing_line": PROCESSING_LINE_UNCLASSIFIED,
            "return_slip_type": "廠內退料",
            "work_order_no": "N/A",
            "internal_work_order_no": "N/A",
            "transfer_slip_no": "",
            "item_no": f"ITEM-{defect_no}",
            "product_name": "Legacy migrated part",
            "qty": 1,
            "category": "原物料",
            "supplier_name": "Legacy Supplier",
            "outsource_supplier_name": "N/A",
            "defect_desc": f"migrated unclassified {defect_no}",
            "status": "處理中",
            "disposition": "",
            "responsibility": "",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        },
    )


class UnclassifiedHintTests(unittest.TestCase):
    """Regression: formal-line pending pages surface a clickable
    「另有 N 筆未分流待整理 →」link when unclassified open records exist, so
    migrated/imported 未分流 data is never silently hidden (see incident:
    line-scoped pages hid 12 open 未分流 records while stats still counted them)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        database.apply_schema(self.conn, with_version=True)
        # One formal-line open record so the page also has real content.
        defect_service.create_defect(
            self.conn,
            {
                "event_date": "2026-04-14",
                "processing_line": PROCESSING_LINE_MATERIAL,
                "return_slip_type": "廠內退料",
                "work_order_no": "5102-260414001",
                "item_no": "ITEM-1001",
                "product_name": "Motor",
                "qty": 5,
                "category": "原物料",
                "supplier_name": "A Supplier",
                "defect_desc": "Scratch",
                "status": "處理中",
                "disposition": "重工",
            },
        )

    def tearDown(self) -> None:
        self.conn.close()

    def test_hint_visible_and_click_emits_when_unclassified_exists(self) -> None:
        _insert_unclassified(self.conn, "NCR-90001")
        widget = DefectListWidget(
            self.conn, workflow="tracking", processing_line=PROCESSING_LINE_MATERIAL
        )
        try:
            btn = widget.unclassified_link_button
            self.assertIsNotNone(btn)
            self.assertFalse(btn.isHidden())
            self.assertIn("未分流待整理", btn.text())
            self.assertIn("1", btn.text())

            fired: list[int] = []
            widget.unclassified_link_requested.connect(lambda: fired.append(1))
            btn.click()
            self.assertEqual(1, len(fired))
        finally:
            widget.close()

    def test_hint_hidden_when_no_unclassified(self) -> None:
        widget = DefectListWidget(
            self.conn, workflow="tracking", processing_line=PROCESSING_LINE_OUTSOURCE
        )
        try:
            self.assertIsNotNone(widget.unclassified_link_button)
            self.assertTrue(widget.unclassified_link_button.isHidden())
        finally:
            widget.close()

    def test_hint_hides_again_after_backlog_cleared(self) -> None:
        _insert_unclassified(self.conn, "NCR-90002")
        widget = DefectListWidget(
            self.conn, workflow="tracking", processing_line=PROCESSING_LINE_MATERIAL
        )
        try:
            self.assertFalse(widget.unclassified_link_button.isHidden())
            # Reclassify the backlog row, then refresh: hint must disappear.
            self.conn.execute(
                "UPDATE defect_records SET processing_line=? WHERE defect_no=?",
                (PROCESSING_LINE_MATERIAL, "NCR-90002"),
            )
            self.conn.commit()
            widget.refresh_data()
            self.assertTrue(widget.unclassified_link_button.isHidden())
        finally:
            widget.close()

    def test_no_hint_button_on_history_page(self) -> None:
        widget = DefectListWidget(self.conn, workflow="trace")
        try:
            self.assertIsNone(widget.unclassified_link_button)
        finally:
            widget.close()

    def test_no_hint_button_on_unclassified_cleanup_page(self) -> None:
        widget = DefectListWidget(
            self.conn, workflow="tracking", processing_line=PROCESSING_LINE_UNCLASSIFIED
        )
        try:
            self.assertIsNone(widget.unclassified_link_button)
        finally:
            widget.close()


if __name__ == "__main__":
    unittest.main()
