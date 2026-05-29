from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from uuid import uuid4

from database import repository


class SupplierDeletionTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_supplier_delete_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _create_supplier(self, name: str) -> str:
        return repository.create_supplier_record(self.conn, supplier_name=name)

    def test_delete_supplier_without_references(self) -> None:
        supplier_id = self._create_supplier("Delete Me")

        repository.delete_supplier_record(self.conn, supplier_id)

        self.assertIsNone(repository.get_supplier(self.conn, supplier_id))

    def test_delete_supplier_referenced_by_products(self) -> None:
        supplier_id = self._create_supplier("Product Ref Supplier")
        secondary_supplier_id = self._create_supplier("Product Ref Supplier 2nd")
        repository.create_product_record(
            self.conn,
            product_code="P-REF-001",
            product_name="Product Ref",
            supplier_id=supplier_id,
            secondary_supplier_id=secondary_supplier_id,
        )

        with self.assertRaises(ValueError) as ctx:
            repository.delete_supplier_record(self.conn, supplier_id)

        self.assertIn("products", str(ctx.exception))
        self.assertIsNotNone(repository.get_supplier(self.conn, supplier_id))

    def test_delete_supplier_referenced_by_products_secondary_source(self) -> None:
        supplier_id = self._create_supplier("Secondary Ref Supplier")
        secondary_supplier_id = self._create_supplier("Secondary Ref Supplier 2nd")
        repository.create_product_record(
            self.conn,
            product_code="P-REF-SEC-001",
            product_name="Product Ref Secondary",
            supplier_id=supplier_id,
            secondary_supplier_id=secondary_supplier_id,
        )

        with self.assertRaises(ValueError) as ctx:
            repository.delete_supplier_record(self.conn, secondary_supplier_id)

        self.assertIn("products", str(ctx.exception))
        self.assertIsNotNone(repository.get_supplier(self.conn, secondary_supplier_id))

    def test_delete_supplier_referenced_by_anomalies(self) -> None:
        supplier_id = self._create_supplier("Anomaly Ref Supplier")
        repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-16",
            supplier_id=supplier_id,
            problem_desc="blocking reference",
        )

        with self.assertRaises(ValueError) as ctx:
            repository.delete_supplier_record(self.conn, supplier_id)

        self.assertIn("anomalies", str(ctx.exception))
        self.assertIsNotNone(repository.get_supplier(self.conn, supplier_id))

    def test_delete_supplier_referenced_by_visits(self) -> None:
        supplier_id = self._create_supplier("Visit Ref Supplier")
        repository.create_visit(
            self.conn,
            visit_date="2026-04-16",
            supplier_id=supplier_id,
            summary="blocking reference",
        )

        with self.assertRaises(ValueError) as ctx:
            repository.delete_supplier_record(self.conn, supplier_id)

        self.assertIn("visits", str(ctx.exception))
        self.assertIsNotNone(repository.get_supplier(self.conn, supplier_id))

    def test_delete_suppliers_partial_success(self) -> None:
        deletable_supplier_id = self._create_supplier("Batch Deletable")
        blocked_supplier_id = self._create_supplier("Batch Blocked")
        blocked_secondary_supplier_id = self._create_supplier("Batch Blocked 2nd")
        repository.create_product_record(
            self.conn,
            product_code="P-REF-002",
            product_name="Batch Product Ref",
            supplier_id=blocked_supplier_id,
            secondary_supplier_id=blocked_secondary_supplier_id,
        )

        result = repository.delete_supplier_records(
            self.conn,
            [deletable_supplier_id, blocked_supplier_id, ""],
        )

        self.assertIn(deletable_supplier_id, result["deleted"])
        failed = {item["id"]: item["reason"] for item in result["failed"]}
        self.assertIn(blocked_supplier_id, failed)
        self.assertIn("", failed)
        self.assertIn("referenced", failed[blocked_supplier_id].lower())
        self.assertIn("required", failed[""].lower())
        self.assertIsNone(repository.get_supplier(self.conn, deletable_supplier_id))
        self.assertIsNotNone(repository.get_supplier(self.conn, blocked_supplier_id))


if __name__ == "__main__":
    unittest.main()
