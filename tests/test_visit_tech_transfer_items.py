from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from uuid import uuid4

from database import repository


class VisitTechTransferItemsTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_visit_tech_transfer_items_{uuid4().hex}.db"
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

    def test_create_visit_defaults_all_transfer_items_to_false(self) -> None:
        supplier_id = self._create_supplier("Visit Transfer Supplier")
        visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-04-18",
            supplier_id=supplier_id,
            summary="transfer defaults",
        )

        detail = repository.get_visit_detail(self.conn, visit_id)
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertFalse(detail["tech_transfer"])
        self.assertFalse(detail["tech_transfer_doc"])
        self.assertFalse(detail["carrier_requirement"])
        self.assertFalse(detail["dispensing_process"])
        self.assertFalse(detail["functional_test"])
        self.assertFalse(detail["packaging_requirement"])

    def test_update_visit_persists_transfer_items_and_enforces_consistency(self) -> None:
        supplier_id = self._create_supplier("Visit Transfer Update Supplier")
        visit_id = repository.create_visit(
            self.conn,
            visit_date="2026-04-18",
            supplier_id=supplier_id,
            summary="transfer update",
        )

        repository.update_visit(
            self.conn,
            visit_id=visit_id,
            visit_date="2026-04-19",
            supplier_id=supplier_id,
            summary="transfer update yes",
            tech_transfer=False,
            functional_test=True,
            packaging_requirement=True,
        )
        detail_after_yes = repository.get_visit_detail(self.conn, visit_id)
        self.assertIsNotNone(detail_after_yes)
        assert detail_after_yes is not None
        self.assertTrue(detail_after_yes["tech_transfer"])
        self.assertTrue(detail_after_yes["functional_test"])
        self.assertTrue(detail_after_yes["packaging_requirement"])

        repository.update_visit(
            self.conn,
            visit_id=visit_id,
            visit_date="2026-04-20",
            supplier_id=supplier_id,
            summary="transfer update no",
            tech_transfer=False,
            tech_transfer_doc=False,
            carrier_requirement=False,
            dispensing_process=False,
            functional_test=False,
            packaging_requirement=False,
        )
        detail_after_no = repository.get_visit_detail(self.conn, visit_id)
        self.assertIsNotNone(detail_after_no)
        assert detail_after_no is not None
        self.assertFalse(detail_after_no["tech_transfer"])
        self.assertFalse(detail_after_no["tech_transfer_doc"])
        self.assertFalse(detail_after_no["carrier_requirement"])
        self.assertFalse(detail_after_no["dispensing_process"])
        self.assertFalse(detail_after_no["functional_test"])
        self.assertFalse(detail_after_no["packaging_requirement"])

    def test_create_schema_backfills_missing_transfer_columns_with_false(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        supplier_id = uuid4().hex
        visit_id = uuid4().hex
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
                secondary_supplier_id TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
                FOREIGN KEY (secondary_supplier_id) REFERENCES suppliers(id)
            );

            CREATE TABLE visits (
                id TEXT PRIMARY KEY,
                visit_date TEXT NOT NULL,
                supplier_id TEXT NOT NULL,
                product_id TEXT,
                product_name TEXT NOT NULL DEFAULT '',
                product_stage TEXT NOT NULL DEFAULT '量產',
                summary TEXT NOT NULL DEFAULT '',
                work_order_no TEXT NOT NULL DEFAULT '',
                production_qty INTEGER NOT NULL DEFAULT 0,
                tech_transfer INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT '已完成' CHECK (status='已完成'),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
            """
        )
        self.conn.execute(
            """
            INSERT INTO suppliers(id, supplier_name, is_active, created_at, updated_at)
            VALUES (?, 'Legacy Transfer Supplier', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (supplier_id,),
        )
        self.conn.execute(
            """
            INSERT INTO visits(
                id, visit_date, supplier_id, product_id, product_name, product_stage, summary,
                work_order_no, production_qty, tech_transfer, status, created_at, updated_at
            )
            VALUES (?, '2026-04-18', ?, NULL, '', '量產', 'legacy transfer visit', '', 0, 1, '已完成', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (visit_id, supplier_id),
        )
        self.conn.commit()

        repository.create_schema(self.conn)

        columns = {
            str(row["name"])
            for row in self.conn.execute("PRAGMA table_info(visits)").fetchall()
        }
        self.assertIn("tech_transfer_doc", columns)
        self.assertIn("carrier_requirement", columns)
        self.assertIn("dispensing_process", columns)
        self.assertIn("functional_test", columns)
        self.assertIn("packaging_requirement", columns)

        detail = repository.get_visit_detail(self.conn, visit_id)
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertTrue(detail["tech_transfer"])
        self.assertFalse(detail["tech_transfer_doc"])
        self.assertFalse(detail["carrier_requirement"])
        self.assertFalse(detail["dispensing_process"])
        self.assertFalse(detail["functional_test"])
        self.assertFalse(detail["packaging_requirement"])


if __name__ == "__main__":
    unittest.main()
