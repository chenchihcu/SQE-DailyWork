import unittest
import sqlite3
import os
import sys

# Add SQE DailyWork root to path so `import ncr.*` resolves (two levels up: ncr/tests -> ncr -> SQE DailyWork)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ncr.db import database, crud
from ncr.services import defect_service, product_service, supplier_service

class TestSupplierSync(unittest.TestCase):
    def setUp(self):
        # Use in-memory database for testing
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        database.apply_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_sync_on_create_defect(self):
        defect_data = {
            "event_date": "2026-04-24",
            "return_slip_type": "廠內退料",
            "work_order_no": "5102-260424001",
            "item_no": "ITEM-001",
            "product_name": "Test Product",
            "qty": 10,
            "supplier_name": "New Supplier A",
            "outsource_supplier_name": "N/A",
            "defect_desc": "Sync Test",
            "category": "原物料",
            "status": "處理中"
        }
        
        defect_service.create_defect(self.conn, defect_data)
        
        # Check if supplier was added to supplier_records
        suppliers = crud.get_suppliers(self.conn, "正式供應商")
        names = [s["name"] for s in suppliers]
        self.assertIn("New Supplier A", names)

    def test_sync_on_update_defect(self):
        # First create a defect
        defect_data = {
            "event_date": "2026-04-24",
            "return_slip_type": "廠內退料",
            "work_order_no": "5102-260424002",
            "item_no": "ITEM-002",
            "product_name": "Test Product B",
            "qty": 5,
            "supplier_name": "Initial Supplier",
            "outsource_supplier_name": "N/A",
            "defect_desc": "Update Test",
            "category": "原物料",
            "status": "處理中"
        }
        defect_no = defect_service.create_defect(self.conn, defect_data)
        
        # Get the ID
        row = self.conn.execute("SELECT id FROM defect_records WHERE defect_no = ?", (defect_no,)).fetchone()
        defect_id = row["id"]
        
        # Update with new supplier
        defect_data["supplier_name"] = "Updated Supplier C"
        defect_service.update_defect(self.conn, defect_id, defect_data)
        
        # Check if updated supplier was added
        suppliers = crud.get_suppliers(self.conn, "正式供應商")
        names = [s["name"] for s in suppliers]
        self.assertIn("Updated Supplier C", names)

    def test_bulk_sync(self):
        # Insert raw defects without sync (using crud directly)
        self.conn.execute(
            "INSERT INTO defect_records (defect_no, event_date, work_order_no, item_no, defect_desc, supplier_name, outsource_supplier_name, created_at, qty) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("NCR-1", "2026-04-24", "WO-3", "ITEM-3", "Bulk 1", "Bulk Supplier X", "N/A", "2026-04-24", 1)
        )
        self.conn.execute(
            "INSERT INTO defect_records (defect_no, event_date, work_order_no, item_no, defect_desc, supplier_name, outsource_supplier_name, created_at, qty) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("NCR-2", "2026-04-24", "WO-4", "ITEM-4", "Bulk 2", "N/A", "Bulk Outsource Y", "2026-04-24", 1)
        )
        self.conn.commit()
        
        # Run bulk sync
        supplier_service.bulk_sync_suppliers_from_all_defects(self.conn)
        
        # Check formal
        formal = [s["name"] for s in crud.get_suppliers(self.conn, "正式供應商")]
        self.assertIn("Bulk Supplier X", formal)
        
        # Check outsource
        outsource = [s["name"] for s in crud.get_suppliers(self.conn, "委外供應商")]
        self.assertIn("Bulk Outsource Y", outsource)

    def test_bulk_product_sync_uses_latest_name_per_item_no(self):
        self.conn.execute(
            "INSERT INTO defect_records (defect_no, event_date, work_order_no, item_no, product_name, defect_desc, created_at, qty) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("NCR-P1", "2026-04-24", "WO-P1", "ITEM-P", "Old Product", "Bulk P1", "2026-04-24", 1),
        )
        self.conn.execute(
            "INSERT INTO defect_records (defect_no, event_date, work_order_no, item_no, product_name, defect_desc, created_at, qty) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("NCR-P2", "2026-04-24", "WO-P2", "ITEM-P", "New Product", "Bulk P2", "2026-04-24", 1),
        )
        self.conn.commit()

        count = product_service.bulk_sync_products_from_all_defects(self.conn)

        products = crud.get_products(self.conn)
        self.assertEqual(count, 1)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["item_no"], "ITEM-P")
        self.assertEqual(products[0]["product_name"], "New Product")

    def test_product_sync_does_not_overwrite_existing_product_name(self):
        self.conn.execute(
            """
            INSERT INTO product_records (item_no, product_name, created_at)
            VALUES (?, ?, ?)
            """,
            ("ITEM-P", "Excel Product", "2026-04-24T08:00:00"),
        )
        self.conn.execute(
            "INSERT INTO defect_records (defect_no, event_date, work_order_no, item_no, product_name, defect_desc, created_at, qty) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("NCR-P3", "2026-04-24", "WO-P3", "ITEM-P", "Old Product", "Bulk P3", "2026-04-24", 1),
        )
        self.conn.commit()

        count = product_service.bulk_sync_products_from_all_defects(self.conn)

        products = crud.get_products(self.conn)
        self.assertEqual(count, 0)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["product_name"], "Excel Product")

    def test_defect_save_does_not_overwrite_existing_product_name(self):
        self.conn.execute(
            """
            INSERT INTO product_records (item_no, product_name, created_at)
            VALUES (?, ?, ?)
            """,
            ("ITEM-P", "Excel Product", "2026-04-24T08:00:00"),
        )
        self.conn.commit()
        defect_data = {
            "event_date": "2026-04-24",
            "return_slip_type": "廠內退料",
            "work_order_no": "5102-260424004",
            "item_no": "ITEM-P",
            "product_name": "Old Product",
            "qty": 1,
            "category": "成品",
            "supplier_name": "Supplier P",
            "outsource_supplier_name": "",
            "defect_desc": "Product sync overwrite guard",
            "status": "處理中",
            "disposition": "",
        }

        defect_service.create_defect(self.conn, defect_data)

        products = crud.get_products(self.conn)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["product_name"], "Excel Product")

if __name__ == "__main__":
    unittest.main()
