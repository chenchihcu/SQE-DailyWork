from __future__ import annotations

import sqlite3
import unittest

from database import repository


class AnomalyRepositoryInvariantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.supplier_a = repository.create_supplier_record(
            self.conn, supplier_name="Invariant Supplier A"
        )
        self.supplier_b = repository.create_supplier_record(
            self.conn, supplier_name="Invariant Supplier B"
        )
        self.product_a = repository.create_product_record(
            self.conn,
            product_code="INV-001",
            product_name="Invariant Product A",
            supplier_id=self.supplier_a,
        )
        self.visit_a = repository.create_visit(
            self.conn,
            visit_date="2026-06-01",
            supplier_id=self.supplier_a,
            product_id=self.product_a,
        )

    def tearDown(self) -> None:
        self.conn.close()

    def _linked_anomaly(self) -> tuple[str, str]:
        result = repository.create_anomaly_with_visit_link(
            self.conn,
            anomaly_date="2026-06-01",
            supplier_id=self.supplier_a,
            product_id=self.product_a,
            problem_desc="linked invariant",
            visit_id=self.visit_a,
            sync_visit=False,
        )
        return str(result["anomaly_id"]), str(result["anomaly_no"])

    def test_explicit_anomaly_number_requires_digits_and_date_prefix(self) -> None:
        with self.assertRaisesRegex(ValueError, "11 碼純數字"):
            repository.create_anomaly_with_visit_link(
                self.conn,
                anomaly_date="2026-06-01",
                supplier_id=self.supplier_a,
                product_id=self.product_a,
                problem_desc="bad number",
                sync_visit=False,
                anomaly_no="BAD",
            )
        with self.assertRaisesRegex(ValueError, "前 8 碼"):
            repository.create_anomaly_with_visit_link(
                self.conn,
                anomaly_date="2026-06-01",
                supplier_id=self.supplier_a,
                product_id=self.product_a,
                problem_desc="bad prefix",
                sync_visit=False,
                anomaly_no="20260602001",
            )

    def test_update_anomaly_number_uses_repository_validator(self) -> None:
        anomaly_id, _ = self._linked_anomaly()
        with self.assertRaisesRegex(ValueError, "11 碼純數字"):
            repository.update_anomaly(
                self.conn,
                anomaly_id=anomaly_id,
                anomaly_date="2026-06-01",
                supplier_id=self.supplier_a,
                product_id=self.product_a,
                problem_desc="bad update",
                anomaly_no="INVALID",
            )

    def test_link_and_supplier_changes_preserve_same_supplier_invariant(self) -> None:
        anomaly_id, anomaly_no = self._linked_anomaly()
        visit_b = repository.create_visit(
            self.conn,
            visit_date="2026-06-01",
            supplier_id=self.supplier_b,
        )
        with self.assertRaisesRegex(ValueError, "Visit supplier"):
            repository.update_anomaly_link(self.conn, anomaly_id, visit_b)
        with self.assertRaisesRegex(ValueError, "Visit supplier"):
            repository.update_anomaly(
                self.conn,
                anomaly_id=anomaly_id,
                anomaly_date="2026-06-01",
                supplier_id=self.supplier_b,
                problem_desc="supplier changed",
                anomaly_no=anomaly_no,
            )
        with self.assertRaisesRegex(ValueError, "linked anomaly supplier"):
            repository.update_visit(
                self.conn,
                visit_id=self.visit_a,
                visit_date="2026-06-01",
                supplier_id=self.supplier_b,
            )


if __name__ == "__main__":
    unittest.main()
