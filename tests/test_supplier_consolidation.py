from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from uuid import uuid4

from database import repository


class SupplierNameCanonicalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_supplier_canonical_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_create_supplier_canonicalizes_suffix_and_blocks_duplicate_company(self) -> None:
        supplier_id = repository.create_supplier_record(
            self.conn,
            supplier_name="台達電子-01",
        )
        created = repository.get_supplier(self.conn, supplier_id)
        self.assertIsNotNone(created)
        assert created is not None
        self.assertEqual("台達電子", created["supplier_name"])

        with self.assertRaises(ValueError) as ctx:
            repository.create_supplier_record(
                self.conn,
                supplier_name="台達電子-b888d01f-受保護",
            )
        self.assertIn("already exists", str(ctx.exception).lower())

    def test_update_and_ensure_supplier_apply_same_canonical_rule(self) -> None:
        supplier_id = repository.create_supplier_record(
            self.conn,
            supplier_name="和碩聯合-33",
        )
        repository.update_supplier_record(
            self.conn,
            supplier_id=supplier_id,
            supplier_name="和碩聯合-db206b2f",
            contact_name="A",
            phone="0900",
        )
        updated = repository.get_supplier(self.conn, supplier_id)
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual("和碩聯合", updated["supplier_name"])

        same_supplier_id = repository.ensure_supplier(
            self.conn,
            "和碩聯合-4ba777df-受保護",
        )
        self.assertEqual(supplier_id, same_supplier_id)


class SupplierConsolidationTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_supplier_merge_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _insert_supplier_raw(
        self,
        *,
        supplier_name: str,
        is_active: bool,
        contact_name: str = "",
        phone: str = "",
        created_at: str,
        updated_at: str,
    ) -> str:
        supplier_id = uuid4().hex
        self.conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, contact_name, phone, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                supplier_id,
                supplier_name,
                contact_name,
                phone,
                1 if is_active else 0,
                created_at,
                updated_at,
            ),
        )
        self.conn.commit()
        return supplier_id

    def _insert_product_raw(
        self,
        *,
        supplier_id: str,
        product_code: str,
        product_name: str,
        secondary_supplier_id: str | None = None,
        is_active: bool,
        created_at: str,
        updated_at: str,
    ) -> str:
        product_id = uuid4().hex
        self.conn.execute(
            """
            INSERT INTO products(
                id, product_code, product_name, supplier_id, secondary_supplier_id,
                is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                product_code,
                product_name,
                supplier_id,
                secondary_supplier_id,
                1 if is_active else 0,
                created_at,
                updated_at,
            ),
        )
        self.conn.commit()
        return product_id

    def test_consolidate_suppliers_merges_entities_and_product_conflicts(self) -> None:
        canonical_supplier = self._insert_supplier_raw(
            supplier_name="台達電子",
            is_active=False,
            created_at="2026-01-01 09:00:00",
            updated_at="2026-01-01 09:00:00",
        )
        numeric_supplier = self._insert_supplier_raw(
            supplier_name="台達電子-01",
            is_active=True,
            created_at="2026-01-02 09:00:00",
            updated_at="2026-01-02 09:00:00",
        )
        hash_supplier = self._insert_supplier_raw(
            supplier_name="台達電子-b888d01f-受保護",
            is_active=False,
            contact_name="Latest Contact",
            phone="0900111222",
            created_at="2026-01-03 09:00:00",
            updated_at="2026-01-10 09:00:00",
        )

        keeper_product = self._insert_product_raw(
            supplier_id=canonical_supplier,
            product_code="P-100",
            product_name="Old Product Name",
            secondary_supplier_id=hash_supplier,
            is_active=False,
            created_at="2026-02-01 09:00:00",
            updated_at="2026-02-01 09:00:00",
        )
        merged_product = self._insert_product_raw(
            supplier_id=numeric_supplier,
            product_code="P-100",
            product_name="New Product Name",
            secondary_supplier_id=hash_supplier,
            is_active=True,
            created_at="2026-02-02 09:00:00",
            updated_at="2026-02-10 09:00:00",
        )
        moved_product = self._insert_product_raw(
            supplier_id=hash_supplier,
            product_code="P-200",
            product_name="Hash Product",
            secondary_supplier_id=numeric_supplier,
            is_active=True,
            created_at="2026-02-03 09:00:00",
            updated_at="2026-02-03 09:00:00",
        )

        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-04-01",
            supplier_id=numeric_supplier,
            product_id=merged_product,
            problem_desc="supplier merge anomaly",
        )
        visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-04-01",
            supplier_id=hash_supplier,
            product_id=moved_product,
            summary="supplier merge visit",
        )

        preview = repository.consolidate_suppliers(self.conn, apply=False)
        self.assertFalse(preview["applied"])
        self.assertTrue(preview["changed"])
        self.assertEqual(1, preview["groups_merged"])
        self.assertEqual(3, preview["suppliers_before"])
        supplier_count_before = self.conn.execute(
            "SELECT COUNT(*) AS c FROM suppliers"
        ).fetchone()["c"]
        self.assertEqual(3, int(supplier_count_before))

        applied = repository.consolidate_suppliers(self.conn, apply=True)
        self.assertTrue(applied["applied"])
        self.assertTrue(applied["changed"])
        self.assertEqual(1, applied["groups_merged"])
        self.assertEqual(2, applied["suppliers_deleted"])
        self.assertEqual(1, applied["product_conflicts_resolved"])

        suppliers = repository.list_suppliers(self.conn, include_inactive=True)
        self.assertEqual(1, len(suppliers))
        merged_supplier = suppliers[0]
        self.assertEqual(canonical_supplier, merged_supplier["id"])
        self.assertEqual("台達電子", merged_supplier["supplier_name"])
        self.assertTrue(merged_supplier["is_active"])
        self.assertEqual("Latest Contact", merged_supplier["contact_name"])
        self.assertEqual("0900111222", merged_supplier["phone"])

        anomaly_row = self.conn.execute(
            "SELECT id, supplier_id, product_id FROM anomalies WHERE anomaly_no = ?",
            (anomaly_no,),
        ).fetchone()
        self.assertIsNotNone(anomaly_row)
        assert anomaly_row is not None
        self.assertEqual(canonical_supplier, anomaly_row["supplier_id"])
        self.assertEqual(keeper_product, anomaly_row["product_id"])

        visit_row = self.conn.execute(
            "SELECT id, supplier_id, product_id FROM visits WHERE id = ?",
            (visit_id,),
        ).fetchone()
        self.assertIsNotNone(visit_row)
        assert visit_row is not None
        self.assertEqual(canonical_supplier, visit_row["supplier_id"])
        self.assertEqual(moved_product, visit_row["product_id"])

        products = self.conn.execute(
            """
            SELECT id, product_code, product_name, supplier_id, secondary_supplier_id, is_active
            FROM products
            ORDER BY product_code
            """
        ).fetchall()
        self.assertEqual(2, len(products))
        product_by_code = {str(row["product_code"]): dict(row) for row in products}
        self.assertIn("P-100", product_by_code)
        self.assertIn("P-200", product_by_code)
        self.assertEqual(keeper_product, product_by_code["P-100"]["id"])
        self.assertEqual("New Product Name", product_by_code["P-100"]["product_name"])
        self.assertEqual(1, int(product_by_code["P-100"]["is_active"]))
        self.assertIsNone(product_by_code["P-100"]["secondary_supplier_id"])
        self.assertEqual(canonical_supplier, product_by_code["P-200"]["supplier_id"])
        self.assertIsNone(product_by_code["P-200"]["secondary_supplier_id"])

        fk_rows = self.conn.execute("PRAGMA foreign_key_check").fetchall()
        self.assertEqual([], fk_rows)

        second_run = repository.consolidate_suppliers(self.conn, apply=True)
        self.assertTrue(second_run["applied"])
        self.assertFalse(second_run["changed"])
        self.assertEqual(0, second_run["groups_merged"])
        self.assertEqual(0, second_run["groups_renamed"])
        self.assertEqual(0, second_run["suppliers_deleted"])
        self.assertEqual(0, second_run["product_conflicts_resolved"])

    def test_consolidate_suppliers_can_rename_single_suffixed_supplier(self) -> None:
        supplier_id = self._insert_supplier_raw(
            supplier_name="廣達電腦-05",
            is_active=True,
            created_at="2026-01-01 09:00:00",
            updated_at="2026-01-01 09:00:00",
        )

        result = repository.consolidate_suppliers(self.conn, apply=True)
        self.assertTrue(result["applied"])
        self.assertTrue(result["changed"])
        self.assertEqual(0, result["groups_merged"])
        self.assertEqual(1, result["groups_renamed"])
        self.assertEqual(0, result["suppliers_deleted"])

        supplier = repository.get_supplier(self.conn, supplier_id)
        self.assertIsNotNone(supplier)
        assert supplier is not None
        self.assertEqual("廣達電腦", supplier["supplier_name"])


if __name__ == "__main__":
    unittest.main()
