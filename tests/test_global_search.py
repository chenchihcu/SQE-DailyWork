from __future__ import annotations

import os
import sqlite3
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from database.repository import create_schema, search_global
from ui.widgets.global_search_dialog import GlobalSearchDialog


class _StubMainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.open_warehouse_history = MagicMock()
        self.open_warehouse_pending_material = MagicMock()
        self.open_warehouse_unclassified_pending = MagicMock()


class GlobalSearchRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_search_global_returns_source_labels(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        create_schema(conn)
        conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, contact_name, department, phone,
                contact_email, category, is_active, created_at, updated_at
            ) VALUES ('sup-1', '測試供應商', '', '', '', '', '', 1, '', '')
            """
        )
        conn.commit()
        rows = search_global(conn, "測試供應商")
        self.assertTrue(rows)
        self.assertEqual("供應商", rows[0]["source"])

    def test_ncr_search_routes_by_processing_line_and_status(self) -> None:
        main_window = _StubMainWindow()
        dialog = GlobalSearchDialog(main_window, parent=None)

        dialog._open_item(self._make_item({
            "source": "不合格品",
            "status": "已結案",
            "processing_line": "原物料",
        }))
        main_window.open_warehouse_history.assert_called_once()

        main_window.open_warehouse_history.reset_mock()
        main_window.open_warehouse_pending_material.reset_mock()
        main_window.open_warehouse_unclassified_pending.reset_mock()
        dialog._open_item(self._make_item({
            "source": "不合格品",
            "status": "待處理",
            "processing_line": "原物料",
        }))
        main_window.open_warehouse_pending_material.assert_called_once()

        main_window.open_warehouse_history.reset_mock()
        main_window.open_warehouse_pending_material.reset_mock()
        main_window.open_warehouse_unclassified_pending.reset_mock()
        dialog._open_item(self._make_item({
            "source": "不合格品",
            "status": "待處理",
            "processing_line": "未分流",
        }))
        main_window.open_warehouse_unclassified_pending.assert_called_once()

    def _make_item(self, row: dict):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QListWidgetItem

        item = QListWidgetItem("row")
        item.setData(Qt.ItemDataRole.UserRole, row)
        return item


if __name__ == "__main__":
    unittest.main()
