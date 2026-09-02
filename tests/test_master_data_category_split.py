"""Master data category split: migration and scoped list filters."""

from __future__ import annotations

import sqlite3
import unittest

from database.product_item_category import (
    ITEM_CATEGORY_FINISHED,
    ITEM_CATEGORY_RAW_MATERIAL,
    ITEM_CATEGORY_SEMI_FINISHED,
    PRODUCT_ITEM_CATEGORY_META_KEY,
    PRODUCT_ITEM_CATEGORY_V2_META_KEY,
    infer_item_category_from_product_code,
)
from database.repository import (
    create_product_record,
    create_schema,
    create_supplier_record,
    get_migration_meta,
    list_products,
    list_suppliers,
)
from database.supplier_category import (
    LEGACY_SUPPLIER_CATEGORY_FORMAL,
    LEGACY_SUPPLIER_CATEGORY_OUTSOURCE_FACTORY_V1,
    LEGACY_SUPPLIER_CATEGORY_RAW_MATERIAL_V1,
    SUPPLIER_CATEGORY_OUTSOURCE_FACTORY,
    SUPPLIER_CATEGORY_RAW_MATERIAL,
    SUPPLIER_CATEGORY_RENAME_META_KEY,
    SUPPLIER_CATEGORY_RENAME_V2_META_KEY,
)


class MasterDataCategoryMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        create_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_supplier_category_rename_migration(self) -> None:
        self.assertEqual(get_migration_meta(self.conn, SUPPLIER_CATEGORY_RENAME_META_KEY), "1")
        self.assertEqual(get_migration_meta(self.conn, SUPPLIER_CATEGORY_RENAME_V2_META_KEY), "1")
        self.conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, contact_name, department, phone, contact_email,
                category, is_active, created_at, updated_at
            ) VALUES ('legacy-formal', '舊正式', '', '', '', '', ?, 1, '2026-01-01', '2026-01-01')
            """,
            (LEGACY_SUPPLIER_CATEGORY_FORMAL,),
        )
        self.conn.commit()
        self.conn.execute(
            "UPDATE suppliers SET category = ? WHERE id = 'legacy-formal'",
            (LEGACY_SUPPLIER_CATEGORY_FORMAL,),
        )
        self.conn.execute(
            "UPDATE suppliers SET category = ? WHERE category = ?",
            (SUPPLIER_CATEGORY_RAW_MATERIAL, LEGACY_SUPPLIER_CATEGORY_FORMAL),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT category FROM suppliers WHERE id = 'legacy-formal'"
        ).fetchone()
        self.assertEqual(str(row["category"]), SUPPLIER_CATEGORY_RAW_MATERIAL)

    def test_supplier_category_rename_v2_maps_legacy_v1_labels(self) -> None:
        self.conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, contact_name, department, phone, contact_email,
                category, is_active, created_at, updated_at
            ) VALUES ('legacy-v1-raw', '舊原料', '', '', '', '', ?, 1, '2026-01-01', '2026-01-01')
            """,
            (LEGACY_SUPPLIER_CATEGORY_RAW_MATERIAL_V1,),
        )
        self.conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, contact_name, department, phone, contact_email,
                category, is_active, created_at, updated_at
            ) VALUES ('legacy-v1-out', '舊委外', '', '', '', '', ?, 1, '2026-01-01', '2026-01-01')
            """,
            (LEGACY_SUPPLIER_CATEGORY_OUTSOURCE_FACTORY_V1,),
        )
        self.conn.commit()
        self.conn.execute(
            "UPDATE suppliers SET category = ? WHERE category = ?",
            (SUPPLIER_CATEGORY_RAW_MATERIAL, LEGACY_SUPPLIER_CATEGORY_RAW_MATERIAL_V1),
        )
        self.conn.execute(
            "UPDATE suppliers SET category = ? WHERE category = ?",
            (
                SUPPLIER_CATEGORY_OUTSOURCE_FACTORY,
                LEGACY_SUPPLIER_CATEGORY_OUTSOURCE_FACTORY_V1,
            ),
        )
        self.conn.commit()
        raw_row = self.conn.execute(
            "SELECT category FROM suppliers WHERE id = 'legacy-v1-raw'"
        ).fetchone()
        out_row = self.conn.execute(
            "SELECT category FROM suppliers WHERE id = 'legacy-v1-out'"
        ).fetchone()
        self.assertEqual(str(raw_row["category"]), SUPPLIER_CATEGORY_RAW_MATERIAL)
        self.assertEqual(str(out_row["category"]), SUPPLIER_CATEGORY_OUTSOURCE_FACTORY)

    def test_infer_item_category_from_product_code(self) -> None:
        self.assertEqual(
            ITEM_CATEGORY_RAW_MATERIAL,
            infer_item_category_from_product_code("012345"),
        )
        self.assertEqual(
            ITEM_CATEGORY_SEMI_FINISHED,
            infer_item_category_from_product_code("A-100"),
        )
        self.assertEqual(
            ITEM_CATEGORY_FINISHED,
            infer_item_category_from_product_code("A-100", current=ITEM_CATEGORY_FINISHED),
        )

    def test_product_item_category_column_and_backfill(self) -> None:
        self.assertEqual(get_migration_meta(self.conn, PRODUCT_ITEM_CATEGORY_META_KEY), "1")
        self.assertEqual(get_migration_meta(self.conn, PRODUCT_ITEM_CATEGORY_V2_META_KEY), "1")
        supplier_id = create_supplier_record(
            self.conn,
            supplier_name="回填供應商",
            category=SUPPLIER_CATEGORY_RAW_MATERIAL,
        )
        product_id = create_product_record(
            self.conn,
            product_code="012345",
            product_name="原物料料號",
            supplier_id=supplier_id,
            item_category=ITEM_CATEGORY_SEMI_FINISHED,
        )
        row = self.conn.execute(
            "SELECT item_category FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        self.assertEqual(str(row["item_category"]), ITEM_CATEGORY_RAW_MATERIAL)

    def test_list_suppliers_and_products_scope_filters(self) -> None:
        create_supplier_record(
            self.conn,
            supplier_name="原料商A",
            category=SUPPLIER_CATEGORY_RAW_MATERIAL,
        )
        create_supplier_record(
            self.conn,
            supplier_name="委外廠B",
            category=SUPPLIER_CATEGORY_OUTSOURCE_FACTORY,
        )
        raw_supplier_id = create_supplier_record(
            self.conn,
            supplier_name="原料商C",
            category=SUPPLIER_CATEGORY_RAW_MATERIAL,
        )
        create_product_record(
            self.conn,
            product_code="SF-001",
            product_name="半成品料",
            supplier_id=raw_supplier_id,
            item_category=ITEM_CATEGORY_SEMI_FINISHED,
        )
        create_product_record(
            self.conn,
            product_code="012345",
            product_name="原物料料",
            supplier_id=raw_supplier_id,
            item_category=ITEM_CATEGORY_RAW_MATERIAL,
        )

        raw_suppliers = list_suppliers(
            self.conn, include_inactive=True, category=SUPPLIER_CATEGORY_RAW_MATERIAL
        )
        self.assertEqual(len(raw_suppliers), 2)
        outsource_suppliers = list_suppliers(
            self.conn,
            include_inactive=True,
            category=SUPPLIER_CATEGORY_OUTSOURCE_FACTORY,
        )
        self.assertEqual(len(outsource_suppliers), 1)

        raw_products = list_products(
            self.conn,
            include_inactive=True,
            item_categories=(ITEM_CATEGORY_RAW_MATERIAL,),
        )
        self.assertEqual(len(raw_products), 1)
        self.assertEqual(raw_products[0]["product_code"], "012345")


if __name__ == "__main__":
    unittest.main()
