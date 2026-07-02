from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from database import repository
from services import master_import_service


class ProductMasterImportServiceTests(unittest.TestCase):
    def create_connection(self, db_path: Path | None = None) -> sqlite3.Connection:
        conn = sqlite3.connect(db_path or ":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(conn)
        return conn

    def write_workbook(self, path: Path, rows: list[tuple[object, ...]]) -> None:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["料號", "產品名稱", "主供應商", "階段"])
        for row in rows:
            worksheet.append(row)
        workbook.save(path)

    def test_import_creates_shared_supplier_product_and_not_warehouse_defect(
        self,
    ) -> None:
        conn = self.create_connection()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                workbook_path = Path(temp_dir) / "erp_products.xlsx"
                self.write_workbook(
                    workbook_path,
                    [("ERP-ITEM-001", "ERP Product A", "ERP Supplier A", "量產")],
                )

                preview = master_import_service.preview_product_master_import(
                    conn,
                    workbook_path,
                )
                self.assertTrue(preview.can_import)
                self.assertEqual(preview.add_count, 1)
                self.assertEqual(preview.supplier_create_count, 1)

                result = master_import_service.apply_product_master_import(
                    conn,
                    preview,
                    source_file=workbook_path,
                )

                self.assertEqual(result.added_count, 1)
                self.assertEqual(result.supplier_created_count, 1)
                self.assertIsNotNone(result.batch_id)
                supplier = conn.execute(
                    "SELECT id FROM suppliers WHERE supplier_name = ?",
                    ("ERP Supplier A",),
                ).fetchone()
                self.assertIsNotNone(supplier)
                product = conn.execute(
                    """
                    SELECT product_name, supplier_id
                    FROM products
                    WHERE product_code = ?
                    """,
                    ("ERP-ITEM-001",),
                ).fetchone()
                self.assertIsNotNone(product)
                assert supplier is not None
                assert product is not None
                self.assertEqual(product["product_name"], "ERP Product A")
                self.assertEqual(product["supplier_id"], supplier["id"])
                defect_count = conn.execute(
                    "SELECT COUNT(*) FROM defect_records"
                ).fetchone()[0]
                self.assertEqual(defect_count, 0)
                anomaly_count = conn.execute("SELECT COUNT(*) FROM anomalies").fetchone()[0]
                visit_count = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
                note_count = conn.execute(
                    "SELECT COUNT(*) FROM visit_defect_notes"
                ).fetchone()[0]
                self.assertEqual(0, anomaly_count)
                self.assertEqual(0, visit_count)
                self.assertEqual(0, note_count)
                batch = conn.execute(
                    """
                    SELECT source_file, status, added_count, supplier_created_count,
                           error_count, backup_path
                    FROM import_batches
                    WHERE id = ?
                    """,
                    (result.batch_id,),
                ).fetchone()
                self.assertIsNotNone(batch)
                assert batch is not None
                self.assertEqual("erp_products.xlsx", batch["source_file"])
                self.assertEqual(master_import_service.IMPORT_BATCH_COMPLETED, batch["status"])
                self.assertEqual(1, batch["added_count"])
                self.assertEqual(1, batch["supplier_created_count"])
                self.assertEqual(0, batch["error_count"])
                row_count = conn.execute(
                    "SELECT COUNT(*) FROM import_batch_rows WHERE batch_id = ?",
                    (result.batch_id,),
                ).fetchone()[0]
                self.assertEqual(1, row_count)
        finally:
            conn.close()

    def test_file_database_import_creates_backup_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sqe_v2.db"
            conn = self.create_connection(db_path)
            try:
                workbook_path = Path(temp_dir) / "erp_products.xlsx"
                self.write_workbook(
                    workbook_path,
                    [("ERP-ITEM-002", "ERP Product B", "ERP Supplier B", "量產")],
                )
                preview = master_import_service.preview_product_master_import(
                    conn,
                    workbook_path,
                )

                result = master_import_service.apply_product_master_import(
                    conn,
                    preview,
                    source_file=workbook_path,
                )

                self.assertIsNotNone(result.backup_path)
                self.assertIsNotNone(result.batch_id)
                assert result.backup_path is not None
                self.assertTrue(result.backup_path.exists())
                backup_conn = sqlite3.connect(result.backup_path)
                try:
                    backup_count = backup_conn.execute(
                        "SELECT COUNT(*) FROM products"
                    ).fetchone()[0]
                finally:
                    backup_conn.close()
                self.assertEqual(backup_count, 0)
            finally:
                conn.close()

    def test_same_product_code_allowed_across_suppliers(self) -> None:
        """Different suppliers may share the same product_code (scoped by supplier)."""
        conn = self.create_connection()
        try:
            conn.execute(
                """
                INSERT INTO suppliers(id, supplier_name, is_active, created_at, updated_at)
                VALUES ('supplier-a', 'Supplier A', 1, '2026-06-02', '2026-06-02')
                """
            )
            conn.execute(
                """
                INSERT INTO suppliers(id, supplier_name, is_active, created_at, updated_at)
                VALUES ('supplier-b', 'Supplier B', 1, '2026-06-02', '2026-06-02')
                """
            )
            conn.execute(
                """
                INSERT INTO products(
                    id, product_code, product_name, product_stage, supplier_id,
                    is_active, created_at, updated_at
                ) VALUES (
                    'product-a', 'ERP-ITEM-003', 'Current Product', '量產',
                    'supplier-a', 1, '2026-06-02', '2026-06-02'
                )
                """
            )
            conn.commit()

            with tempfile.TemporaryDirectory() as temp_dir:
                workbook_path = Path(temp_dir) / "erp_products.xlsx"
                self.write_workbook(
                    workbook_path,
                    [("ERP-ITEM-003", "Supplier B Product", "Supplier B", "量產")],
                )

                preview = master_import_service.preview_product_master_import(
                    conn,
                    workbook_path,
                )
                self.assertTrue(preview.can_import)
                self.assertEqual(preview.error_count, 0)
                result = master_import_service.apply_product_master_import(
                    conn,
                    preview,
                    source_file=workbook_path,
                )
                self.assertEqual(result.added_count, 1)

                # Original product under Supplier A unchanged
                product_a = conn.execute(
                    """
                    SELECT product_name, supplier_id
                    FROM products
                    WHERE product_code = 'ERP-ITEM-003' AND supplier_id = 'supplier-a'
                    """
                ).fetchone()
                self.assertIsNotNone(product_a)
                assert product_a is not None
                self.assertEqual(product_a["product_name"], "Current Product")

                # New product created under Supplier B
                product_b = conn.execute(
                    """
                    SELECT product_name, supplier_id
                    FROM products
                    WHERE product_code = 'ERP-ITEM-003' AND supplier_id = 'supplier-b'
                    """
                ).fetchone()
                self.assertIsNotNone(product_b)
                assert product_b is not None
                self.assertEqual(product_b["product_name"], "Supplier B Product")
        finally:
            conn.close()

    def test_apply_updates_existing_product_when_supplier_is_newly_created(
        self,
    ) -> None:
        """Regression test for audit finding A2: a product that already
        exists with no supplier assigned, imported under a brand-new
        supplier name (absent from the DB at preview time), must be
        updated rather than raising "Product disappeared" and rolling back
        the whole batch."""
        conn = self.create_connection()
        try:
            conn.execute(
                """
                INSERT INTO products(
                    id, product_code, product_name, product_stage, supplier_id,
                    is_active, created_at, updated_at
                ) VALUES (
                    'product-orphan', 'ERP-ITEM-005', 'Old Name', '量產',
                    NULL, 1, '2026-06-04', '2026-06-04'
                )
                """
            )
            conn.commit()

            with tempfile.TemporaryDirectory() as temp_dir:
                workbook_path = Path(temp_dir) / "erp_products.xlsx"
                self.write_workbook(
                    workbook_path,
                    [("ERP-ITEM-005", "New Name From ERP", "Brand New Supplier", "量產")],
                )

                preview = master_import_service.preview_product_master_import(
                    conn,
                    workbook_path,
                )
                self.assertTrue(preview.can_import)
                self.assertEqual(preview.error_count, 0)
                self.assertEqual(preview.update_count, 1)
                self.assertEqual(preview.supplier_create_count, 1)

                # Before the A2 fix, this raised sqlite3.IntegrityError and
                # rolled back the whole batch.
                result = master_import_service.apply_product_master_import(
                    conn,
                    preview,
                    source_file=workbook_path,
                )

                self.assertEqual(1, result.updated_count)
                self.assertEqual(1, result.supplier_created_count)
                product = conn.execute(
                    "SELECT product_name, supplier_id FROM products WHERE product_code = ?",
                    ("ERP-ITEM-005",),
                ).fetchone()
                self.assertIsNotNone(product)
                assert product is not None
                self.assertEqual("New Name From ERP", product["product_name"])
                supplier = conn.execute(
                    "SELECT id FROM suppliers WHERE supplier_name = ?",
                    ("Brand New Supplier",),
                ).fetchone()
                self.assertIsNotNone(supplier)
                assert supplier is not None
                self.assertEqual(supplier["id"], product["supplier_id"])
        finally:
            conn.close()

    def test_no_write_import_records_skipped_batch(self) -> None:
        conn = self.create_connection()
        try:
            conn.execute(
                """
                INSERT INTO suppliers(id, supplier_name, is_active, created_at, updated_at)
                VALUES ('supplier-a', 'ERP Supplier C', 1, '2026-06-03', '2026-06-03')
                """
            )
            conn.execute(
                """
                INSERT INTO products(
                    id, product_code, product_name, product_stage, supplier_id,
                    is_active, created_at, updated_at
                ) VALUES (
                    'product-c', 'ERP-ITEM-004', 'ERP Product C', '量產',
                    'supplier-a', 1, '2026-06-03', '2026-06-03'
                )
                """
            )
            conn.commit()
            with tempfile.TemporaryDirectory() as temp_dir:
                workbook_path = Path(temp_dir) / "erp_products.xlsx"
                self.write_workbook(
                    workbook_path,
                    [("ERP-ITEM-004", "ERP Product C", "ERP Supplier C", "量產")],
                )
                preview = master_import_service.preview_product_master_import(
                    conn,
                    workbook_path,
                )

                result = master_import_service.apply_product_master_import(
                    conn,
                    preview,
                    source_file=workbook_path,
                )

                self.assertEqual(0, result.added_count)
                self.assertEqual(0, result.updated_count)
                self.assertIsNone(result.backup_path)
                self.assertIsNotNone(result.batch_id)
                batch = conn.execute(
                    "SELECT status, skipped_count FROM import_batches WHERE id = ?",
                    (result.batch_id,),
                ).fetchone()
                self.assertIsNotNone(batch)
                assert batch is not None
                self.assertEqual(master_import_service.IMPORT_BATCH_SKIPPED, batch["status"])
                self.assertEqual(1, batch["skipped_count"])
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
