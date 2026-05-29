from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from uuid import uuid4

from database import repository


class ProductSpecRemovalTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_product_spec_remove_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _table_columns(self, table_name: str) -> set[str]:
        rows = self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row["name"]) for row in rows}

    def test_create_schema_migrates_legacy_products_without_spec_desc(self) -> None:
        supplier_id = uuid4().hex
        product_id = uuid4().hex
        self.conn.executescript(
            """
            CREATE TABLE suppliers (
                id TEXT PRIMARY KEY,
                supplier_name TEXT NOT NULL UNIQUE,
                contact_name TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE products (
                id TEXT PRIMARY KEY,
                product_code TEXT NOT NULL,
                product_name TEXT NOT NULL,
                spec_desc TEXT NOT NULL DEFAULT '',
                supplier_id TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            );

            CREATE UNIQUE INDEX idx_products_global_code
                ON products(product_code)
                WHERE supplier_id IS NULL;
            CREATE UNIQUE INDEX idx_products_supplier_code
                ON products(supplier_id, product_code)
                WHERE supplier_id IS NOT NULL;
            CREATE INDEX idx_products_supplier ON products(supplier_id);
            CREATE INDEX idx_products_active ON products(is_active);
            """
        )
        self.conn.execute(
            """
            INSERT INTO suppliers(id, supplier_name, contact_name, phone, is_active, created_at, updated_at)
            VALUES (?, 'Legacy Supplier', '', '', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (supplier_id,),
        )
        self.conn.execute(
            """
            INSERT INTO products(
                id, product_code, product_name, spec_desc, supplier_id, is_active, created_at, updated_at
            )
            VALUES (?, 'LEG-001', 'Legacy Product', 'Legacy Spec', ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (product_id, supplier_id),
        )
        self.conn.commit()

        repository.create_schema(self.conn)

        product_columns = self._table_columns("products")
        self.assertNotIn("spec_desc", product_columns)
        self.assertEqual(
            product_columns,
            {
                "id",
                "product_code",
                "product_name",
                "product_stage",
                "supplier_id",
                "secondary_supplier_id",
                "is_active",
                "created_at",
                "updated_at",
            },
        )
        row = self.conn.execute(
            """
            SELECT id, product_code, product_name, product_stage, supplier_id, is_active
            FROM products
            WHERE id = ?
            """,
            (product_id,),
        ).fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(str(row["product_code"]), "LEG-001")
        self.assertEqual(str(row["product_name"]), "Legacy Product")
        self.assertEqual(str(row["product_stage"]), "量產")
        self.assertEqual(str(row["supplier_id"]), supplier_id)
        self.assertEqual(int(row["is_active"]), 1)

        index_rows = self.conn.execute("PRAGMA index_list(products)").fetchall()
        index_names = {str(row["name"]) for row in index_rows}
        self.assertIn("idx_products_global_code", index_names)
        self.assertIn("idx_products_supplier_code", index_names)
        self.assertIn("idx_products_supplier", index_names)
        self.assertIn("idx_products_secondary_supplier", index_names)
        self.assertIn("idx_products_active", index_names)

    def test_product_flow_does_not_expose_spec_desc(self) -> None:
        repository.create_schema(self.conn)
        supplier_id = repository.create_supplier_record(
            self.conn, supplier_name="Product Flow Supplier"
        )
        secondary_supplier_id = repository.create_supplier_record(
            self.conn, supplier_name="Product Flow Supplier 2nd"
        )

        product_id = repository.create_product_record(
            self.conn,
            product_code="FLOW-001",
            product_name="Flow Product",
            supplier_id=supplier_id,
            secondary_supplier_id=secondary_supplier_id,
        )
        repository.update_product_record(
            self.conn,
            product_id=product_id,
            product_code="FLOW-001",
            product_name="Flow Product Updated",
            supplier_id=supplier_id,
            secondary_supplier_id=secondary_supplier_id,
        )

        listed = repository.list_products(self.conn, include_inactive=True)
        self.assertEqual(len(listed), 1)
        self.assertNotIn("spec_desc", listed[0])
        self.assertEqual(listed[0]["product_name"], "Flow Product Updated")
        self.assertEqual(listed[0]["product_stage"], "量產")
        self.assertEqual(listed[0]["secondary_supplier_id"], secondary_supplier_id)

        fetched = repository.get_product(self.conn, product_id)
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertNotIn("spec_desc", fetched)
        self.assertEqual(fetched["product_name"], "Flow Product Updated")
        self.assertEqual(fetched["product_stage"], "量產")
        self.assertEqual(fetched["secondary_supplier_id"], secondary_supplier_id)

        active_for_supplier = repository.list_active_products_for_supplier(
            self.conn, supplier_id
        )
        self.assertEqual(len(active_for_supplier), 1)
        self.assertNotIn("spec_desc", active_for_supplier[0])
        self.assertEqual(active_for_supplier[0]["id"], product_id)
        self.assertEqual(active_for_supplier[0]["product_stage"], "量產")

    def test_create_schema_migrates_legacy_status_values_to_zh(self) -> None:
        supplier_id = uuid4().hex
        visit_id = uuid4().hex
        anomaly_open_id = uuid4().hex
        anomaly_closed_id = uuid4().hex
        self.conn.executescript(
            """
            CREATE TABLE suppliers (
                id TEXT PRIMARY KEY,
                supplier_name TEXT NOT NULL UNIQUE,
                contact_name TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE products (
                id TEXT PRIMARY KEY,
                product_code TEXT NOT NULL,
                product_name TEXT NOT NULL,
                supplier_id TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
            );

            CREATE TABLE visits (
                id TEXT PRIMARY KEY,
                visit_date TEXT NOT NULL,
                supplier_id TEXT NOT NULL,
                product_id TEXT,
                product_name TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                work_order_no TEXT NOT NULL DEFAULT '',
                production_qty INTEGER NOT NULL DEFAULT 0,
                tech_transfer INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'COMPLETED' CHECK (status='COMPLETED'),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE anomalies (
                id TEXT PRIMARY KEY,
                anomaly_no TEXT NOT NULL UNIQUE,
                anomaly_date TEXT NOT NULL,
                supplier_id TEXT NOT NULL,
                visit_id TEXT,
                product_id TEXT,
                problem_desc TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                product_lot_no TEXT NOT NULL DEFAULT '',
                product_name TEXT NOT NULL DEFAULT '',
                outsource_work_order TEXT NOT NULL DEFAULT '',
                batch_qty INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED')),
                improvement_desc TEXT NOT NULL DEFAULT '',
                closed_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
                FOREIGN KEY (visit_id) REFERENCES visits(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
            """
        )
        self.conn.execute(
            """
            INSERT INTO suppliers(id, supplier_name, is_active, created_at, updated_at)
            VALUES (?, 'Status Legacy Supplier', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (supplier_id,),
        )
        self.conn.execute(
            """
            INSERT INTO visits(
                id, visit_date, supplier_id, product_id, product_name, summary,
                work_order_no, production_qty, tech_transfer, status, created_at, updated_at
            )
            VALUES (?, '2026-04-16', ?, NULL, '', 'legacy visit', '', 0, 0, 'COMPLETED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (visit_id, supplier_id),
        )
        self.conn.execute(
            """
            INSERT INTO anomalies(
                id, anomaly_no, anomaly_date, supplier_id, visit_id, product_id, problem_desc,
                category, product_lot_no, product_name, outsource_work_order, batch_qty,
                status, improvement_desc, closed_at, created_at, updated_at
            )
            VALUES (?, 'ANM-OPEN', '2026-04-16', ?, ?, NULL, 'legacy open', '', '', '', '', 0, 'OPEN', '', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (anomaly_open_id, supplier_id, visit_id),
        )
        self.conn.execute(
            """
            INSERT INTO anomalies(
                id, anomaly_no, anomaly_date, supplier_id, visit_id, product_id, problem_desc,
                category, product_lot_no, product_name, outsource_work_order, batch_qty,
                status, improvement_desc, closed_at, created_at, updated_at
            )
            VALUES (?, 'ANM-CLOSED', '2026-04-16', ?, ?, NULL, 'legacy closed', '', '', '', '', 0, 'CLOSED', 'fixed', '2026-04-18', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (anomaly_closed_id, supplier_id, visit_id),
        )
        self.conn.commit()

        repository.create_schema(self.conn)

        anomaly_statuses = {
            str(row["status"])
            for row in self.conn.execute("SELECT DISTINCT status FROM anomalies").fetchall()
        }
        self.assertEqual({"待處理", "已結案"}, anomaly_statuses)
        visit_statuses = {
            str(row["status"])
            for row in self.conn.execute("SELECT DISTINCT status FROM visits").fetchall()
        }
        self.assertEqual({"已完成"}, visit_statuses)
        anomaly_stages = {
            str(row["product_stage"])
            for row in self.conn.execute("SELECT DISTINCT product_stage FROM anomalies").fetchall()
        }
        visit_stages = {
            str(row["product_stage"])
            for row in self.conn.execute("SELECT DISTINCT product_stage FROM visits").fetchall()
        }
        self.assertEqual({"量產"}, anomaly_stages)
        self.assertEqual({"量產"}, visit_stages)

        anomaly_table_sql = str(
            self.conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='anomalies'"
            ).fetchone()["sql"]
        )
        self.assertIn("product_stage", anomaly_table_sql)
        self.assertIn("待處理", anomaly_table_sql)
        self.assertIn("已結案", anomaly_table_sql)
        self.assertNotIn("'OPEN'", anomaly_table_sql)
        self.assertNotIn("'CLOSED'", anomaly_table_sql)

        visit_table_sql = str(
            self.conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='visits'"
            ).fetchone()["sql"]
        )
        self.assertIn("product_stage", visit_table_sql)
        self.assertIn("已完成", visit_table_sql)
        self.assertNotIn("'COMPLETED'", visit_table_sql)

        summary = repository.get_dashboard_summary(self.conn)
        self.assertEqual(1, summary["open_count"])
        self.assertEqual(1, summary["closed_count"])

    def test_create_product_requires_primary_supplier_and_secondary_is_optional(self) -> None:
        repository.create_schema(self.conn)
        supplier_a = repository.create_supplier_record(self.conn, supplier_name="Supplier A")
        supplier_b = repository.create_supplier_record(self.conn, supplier_name="Supplier B")

        with self.assertRaises(ValueError) as ctx_primary:
            repository.create_product_record(
                self.conn,
                product_code="RULE-001",
                product_name="Rule Product",
                supplier_id="",
                secondary_supplier_id=supplier_b,
            )
        self.assertIn("Supplier is required", str(ctx_primary.exception))

        optional_secondary_id = repository.create_product_record(
            self.conn,
            product_code="RULE-001",
            product_name="Rule Product",
            supplier_id=supplier_a,
            secondary_supplier_id="",
        )
        optional_secondary_product = repository.get_product(self.conn, optional_secondary_id)
        self.assertIsNotNone(optional_secondary_product)
        assert optional_secondary_product is not None
        self.assertIsNone(optional_secondary_product.get("secondary_supplier_id"))

        with self.assertRaises(ValueError) as ctx_same:
            repository.create_product_record(
                self.conn,
                product_code="RULE-002",
                product_name="Rule Product",
                supplier_id=supplier_a,
                secondary_supplier_id=supplier_a,
            )
        self.assertIn(
            "Secondary supplier must be different from primary supplier",
            str(ctx_same.exception),
        )

        product_id = repository.create_product_record(
            self.conn,
            product_code="RULE-003",
            product_name="Rule Product",
            supplier_id=supplier_a,
            secondary_supplier_id=supplier_b,
        )
        self.assertTrue(bool(product_id))

    def test_update_product_allows_clearing_secondary_source(self) -> None:
        repository.create_schema(self.conn)
        supplier_a = repository.create_supplier_record(self.conn, supplier_name="Supplier A")
        supplier_b = repository.create_supplier_record(self.conn, supplier_name="Supplier B")
        product_id = repository.create_product_record(
            self.conn,
            product_code="UPD-001",
            product_name="Update Optional Secondary",
            supplier_id=supplier_a,
            secondary_supplier_id=supplier_b,
        )

        repository.update_product_record(
            self.conn,
            product_id=product_id,
            product_code="UPD-001",
            product_name="Update Optional Secondary",
            supplier_id=supplier_a,
            secondary_supplier_id="",
        )
        updated_empty = repository.get_product(self.conn, product_id)
        self.assertIsNotNone(updated_empty)
        assert updated_empty is not None
        self.assertIsNone(updated_empty.get("secondary_supplier_id"))

        repository.update_product_record(
            self.conn,
            product_id=product_id,
            product_code="UPD-001",
            product_name="Update Optional Secondary",
            supplier_id=supplier_a,
            secondary_supplier_id=None,
        )
        updated_none = repository.get_product(self.conn, product_id)
        self.assertIsNotNone(updated_none)
        assert updated_none is not None
        self.assertIsNone(updated_none.get("secondary_supplier_id"))

    def test_product_code_is_globally_unique_across_suppliers(self) -> None:
        repository.create_schema(self.conn)
        supplier_a = repository.create_supplier_record(self.conn, supplier_name="Supplier A")
        supplier_b = repository.create_supplier_record(self.conn, supplier_name="Supplier B")
        supplier_c = repository.create_supplier_record(self.conn, supplier_name="Supplier C")

        repository.create_product_record(
            self.conn,
            product_code="GLOBAL-001",
            product_name="Global A",
            supplier_id=supplier_a,
            secondary_supplier_id=supplier_b,
        )

        with self.assertRaises(ValueError) as ctx_create:
            repository.create_product_record(
                self.conn,
                product_code="GLOBAL-001",
                product_name="Global B",
                supplier_id=supplier_c,
                secondary_supplier_id=supplier_a,
            )
        self.assertIn("Product code already exists", str(ctx_create.exception))

        product_id = repository.create_product_record(
            self.conn,
            product_code="GLOBAL-002",
            product_name="Global C",
            supplier_id=supplier_c,
            secondary_supplier_id=supplier_a,
        )
        with self.assertRaises(ValueError) as ctx_update:
            repository.update_product_record(
                self.conn,
                product_id=product_id,
                product_code="GLOBAL-001",
                product_name="Global C Updated",
                supplier_id=supplier_c,
                secondary_supplier_id=supplier_a,
            )
        self.assertIn("Product code already exists", str(ctx_update.exception))

    def test_list_active_products_for_supplier_matches_secondary_source(self) -> None:
        repository.create_schema(self.conn)
        supplier_a = repository.create_supplier_record(self.conn, supplier_name="Supplier A")
        supplier_b = repository.create_supplier_record(self.conn, supplier_name="Supplier B")

        product_id = repository.create_product_record(
            self.conn,
            product_code="SEC-001",
            product_name="Secondary Visible",
            supplier_id=supplier_a,
            secondary_supplier_id=supplier_b,
        )

        for_primary = repository.list_active_products_for_supplier(self.conn, supplier_a)
        for_secondary = repository.list_active_products_for_supplier(self.conn, supplier_b)

        self.assertEqual([product_id], [item["id"] for item in for_primary])
        self.assertEqual([product_id], [item["id"] for item in for_secondary])

    def test_enable_product_allows_missing_secondary_source(self) -> None:
        repository.create_schema(self.conn)
        supplier_a = repository.create_supplier_record(self.conn, supplier_name="Supplier A")
        supplier_b = repository.create_supplier_record(self.conn, supplier_name="Supplier B")
        product_id = repository.create_product_record(
            self.conn,
            product_code="ENB-001",
            product_name="Enable Rule Product",
            supplier_id=supplier_a,
            secondary_supplier_id=supplier_b,
        )
        self.conn.execute(
            """
            UPDATE products
            SET is_active = 0, secondary_supplier_id = NULL
            WHERE id = ?
            """,
            (product_id,),
        )
        self.conn.commit()

        repository.set_product_active(self.conn, product_id, True)
        enabled = repository.get_product(self.conn, product_id)
        self.assertIsNotNone(enabled)
        assert enabled is not None
        self.assertTrue(bool(enabled.get("is_active")))
        self.assertIsNone(enabled.get("secondary_supplier_id"))


if __name__ == "__main__":
    unittest.main()
