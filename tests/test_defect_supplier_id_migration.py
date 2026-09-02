from __future__ import annotations

import sqlite3
import unittest

from database.repo_helpers import get_migration_meta
from database.repository import create_schema


def _insert_defect(
    conn: sqlite3.Connection,
    defect_no: str,
    supplier_name: str,
    processing_line: str = "原物料",
) -> None:
    conn.execute(
        """
        INSERT INTO defect_records(
            defect_no, event_date, processing_line, supplier_name,
            item_no, qty, defect_desc, status, created_at
        ) VALUES (?, '2026-08-01', ?, ?, 'PN-001', 1, '測試不良', '待處理', '2026-08-01')
        """,
        (defect_no, processing_line, supplier_name),
    )


class DefectSupplierIdMigrationTests(unittest.TestCase):
    def test_backfill_matches_supplier_by_exact_name(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        create_schema(conn)
        conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, contact_name, department, phone,
                contact_email, category, is_active
            ) VALUES ('sup-1', '甲供應商', '', '', '', '', '原物料供應商', 1)
            """
        )
        _insert_defect(conn, "NCR-10001", "甲供應商")
        conn.commit()
        conn.execute(
            "DELETE FROM migration_meta WHERE key = 'defect_supplier_id_backfill_v1'"
        )
        create_schema(conn)
        row = conn.execute(
            "SELECT supplier_id FROM defect_records WHERE defect_no = 'NCR-10001'"
        ).fetchone()
        self.assertEqual("sup-1", row["supplier_id"])

    def test_unmatched_name_stays_null(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        create_schema(conn)
        _insert_defect(conn, "NCR-10002", "未知供應商")
        conn.commit()
        row = conn.execute(
            "SELECT supplier_id FROM defect_records WHERE defect_no = 'NCR-10002'"
        ).fetchone()
        self.assertIsNone(row["supplier_id"])

    def test_backfill_meta_gate_prevents_rerun(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        create_schema(conn)
        self.assertEqual("1", get_migration_meta(conn, "defect_supplier_id_backfill_v1"))
        _insert_defect(conn, "NCR-10003", "晚加入供應商")
        conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, contact_name, department, phone,
                contact_email, category, is_active
            ) VALUES ('sup-late', '晚加入供應商', '', '', '', '', '原物料供應商', 1)
            """
        )
        conn.commit()
        row = conn.execute(
            "SELECT supplier_id FROM defect_records WHERE defect_no = 'NCR-10003'"
        ).fetchone()
        self.assertIsNone(row["supplier_id"])

    def test_supplier_name_unique_constraint(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        create_schema(conn)
        indexes = conn.execute("PRAGMA index_list(suppliers)").fetchall()
        unique_on_name = False
        for index in indexes:
            if not index["unique"]:
                continue
            columns = conn.execute(f"PRAGMA index_info({index['name']})").fetchall()
            if any(col["name"] == "supplier_name" for col in columns):
                unique_on_name = True
        self.assertTrue(unique_on_name)


if __name__ == "__main__":
    unittest.main()
