"""Repository: seed products from anomalies creates inactive rows until user enables them."""

from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from uuid import uuid4

from database import repository


class SeedProductsFromAnomaliesTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp = Path("scratch")
        base_tmp.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp / f"sqe_seed_products_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_seeded_auto_products_are_not_active(self) -> None:
        supplier_id = uuid4().hex
        self.conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, contact_name, phone, is_active, created_at, updated_at
            ) VALUES (?, 'S-Seed', '', '', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (supplier_id,),
        )
        self.conn.execute(
            """
            INSERT INTO anomalies(
                id, anomaly_no, anomaly_date, supplier_id, problem_desc,
                category, product_lot_no, product_name, status, improvement_desc, created_at, updated_at
            ) VALUES (
                ?, '20260418001', '2026-04-18', ?, 'p', '', '', 'Seed Prod X',
                '待處理', '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """,
            (uuid4().hex, supplier_id),
        )
        self.conn.commit()

        report = repository.seed_products_from_anomalies(self.conn)
        self.assertTrue(bool(report.get("seeded")))
        row = self.conn.execute(
            "SELECT is_active FROM products WHERE product_name = ? AND supplier_id = ?",
            ("Seed Prod X", supplier_id),
        ).fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(0, int(row["is_active"]))


if __name__ == "__main__":
    unittest.main()
