from __future__ import annotations

import sqlite3
import unittest

from database.repository import create_schema


class Supplier360DataContractTests(unittest.TestCase):
    def test_supplier_relationship_and_ncr_traceability_columns_exist(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        create_schema(conn)
        defect_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(defect_records)").fetchall()
        }
        anomaly_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(anomalies)").fetchall()
        }
        self.assertIn("supplier_id", defect_columns)
        self.assertIn("source_defect_no", anomaly_columns)
        self.assertIn("anomaly_source", anomaly_columns)
        self.assertIn("material_receipt_no", anomaly_columns)
        self.assertIn("internal_work_order_no", anomaly_columns)
        self.assertIn("outsource_receipt_no", anomaly_columns)

    def test_global_search_returns_source_labels(self) -> None:
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
        from database.repository import search_global

        rows = search_global(conn, "測試供應商")
        self.assertTrue(rows)
        self.assertEqual("供應商", rows[0]["source"])


if __name__ == "__main__":
    unittest.main()
