from __future__ import annotations

import os
import sqlite3
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from database.repository import create_schema, search_global
from database.supplier_category import (
    SUPPLIER_CATEGORY_OUTSOURCE_FACTORY,
    SUPPLIER_CATEGORY_RAW_MATERIAL,
)
from ui.widgets.global_search_dialog import GlobalSearchDialog


class _StubMainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.open_warehouse_history = MagicMock()
        self.open_warehouse_pending_material = MagicMock()
        self.open_warehouse_unclassified_pending = MagicMock()
        self.open_master_raw_supplier = MagicMock()
        self.open_master_outsource_supplier = MagicMock()
        self.open_master_raw_material = MagicMock()
        self.open_master_semi_finished = MagicMock()


class GlobalSearchRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_search_global_returns_source_labels(self) -> None:
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.row_factory = sqlite3.Row
        create_schema(conn)
        conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, contact_name, department, phone,
                contact_email, category, is_active, created_at, updated_at
            ) VALUES ('sup-1', '測試供應商', '', '', '', '', ?, 1, '', '')
            """,
            (SUPPLIER_CATEGORY_RAW_MATERIAL,),
        )
        conn.commit()
        rows = search_global(conn, "測試供應商")
        self.assertTrue(rows)
        self.assertEqual("供應商", rows[0]["source"])
        self.assertEqual(SUPPLIER_CATEGORY_RAW_MATERIAL, rows[0]["category"])

    def test_search_global_includes_products_with_item_category(self) -> None:
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.row_factory = sqlite3.Row
        create_schema(conn)
        conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, contact_name, department, phone,
                contact_email, category, is_active, created_at, updated_at
            ) VALUES ('sup-1', 'Alpha', '', '', '', '', ?, 1, '2026-01-01', '2026-01-01')
            """,
            (SUPPLIER_CATEGORY_RAW_MATERIAL,),
        )
        conn.execute(
            """
            INSERT INTO products(
                id, product_code, product_name, product_stage, supplier_id,
                secondary_supplier_id, item_category, is_active, created_at, updated_at
            ) VALUES (
                'prd-1', 'RM-001', '原物料品', '量產', 'sup-1', NULL, '原物料', 1,
                '2026-01-01', '2026-01-01'
            )
            """
        )
        conn.commit()
        rows = search_global(conn, "RM-001")
        product_rows = [row for row in rows if row.get("source") == "產品"]
        self.assertEqual(1, len(product_rows))
        self.assertEqual("原物料", product_rows[0]["item_category"])

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

    def test_master_search_routes_by_supplier_category_and_item_category(self) -> None:
        main_window = _StubMainWindow()
        dialog = GlobalSearchDialog(main_window, parent=None)

        dialog._open_item(self._make_item({
            "source": "供應商",
            "ref_no": "委外-A",
            "category": SUPPLIER_CATEGORY_OUTSOURCE_FACTORY,
        }))
        main_window.open_master_outsource_supplier.assert_called_once_with("委外-A")

        main_window.open_master_outsource_supplier.reset_mock()
        main_window.open_master_raw_supplier.reset_mock()
        dialog._open_item(self._make_item({
            "source": "供應商",
            "ref_no": "原料-A",
            "category": SUPPLIER_CATEGORY_RAW_MATERIAL,
        }))
        main_window.open_master_raw_supplier.assert_called_once_with("原料-A")

        main_window.open_master_raw_material.reset_mock()
        main_window.open_master_semi_finished.reset_mock()
        dialog._open_item(self._make_item({
            "source": "產品",
            "ref_no": "RM-100",
            "item_category": "原物料",
        }))
        main_window.open_master_raw_material.assert_called_once_with("RM-100")

        dialog._open_item(self._make_item({
            "source": "產品",
            "ref_no": "SF-200",
            "item_category": "半成品",
        }))
        main_window.open_master_semi_finished.assert_called_once_with("SF-200")

    def _make_item(self, row: dict):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QListWidgetItem

        item = QListWidgetItem("stub")
        item.setData(Qt.ItemDataRole.UserRole, row)
        return item


if __name__ == "__main__":
    unittest.main()
