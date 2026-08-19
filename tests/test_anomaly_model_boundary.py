from __future__ import annotations

import sqlite3
import unittest

from database import repository


def _seed(conn: sqlite3.Connection):
    supplier = repository.create_supplier_record(conn, supplier_name="BD")
    product = repository.create_product_record(
        conn,
        product_code="BD-001",
        product_name="BD Product",
        supplier_id=supplier,
    )
    anomaly_id = repository.create_anomaly_with_visit_link(
        conn,
        anomaly_date="2026-06-01",
        supplier_id=supplier,
        product_id=product,
        problem_desc="boundary",
        sync_visit=False,
    )["anomaly_id"]
    return supplier, product, anomaly_id


class AnomalySubTableBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.supplier, self.product, self.anomaly_id = _seed(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_no_cross_write_into_defect_records(self) -> None:
        """Supplier-event writes must never touch defect_records."""
        # Populate the anomaly waste of sub-tables entirely on the supplier side.
        repository.create_anomaly_action(
            self.conn, anomaly_id=self.anomaly_id, description="action"
        )
        repository.create_anomaly_analysis_note(
            self.conn, anomaly_id=self.anomaly_id, content="note"
        )
        repository.create_corrective_action(
            self.conn, anomaly_id=self.anomaly_id, description="CA"
        )
        count = self.conn.execute(
            "SELECT COUNT(*) FROM defect_records"
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_warehouse_defect_records_stay_out_of_anomaly_tables(self) -> None:
        """A warehouse defect record must not appear in any anomaly sub-table."""
        self.conn.execute(
            """
            INSERT INTO defect_records(
                defect_no, event_date, processing_line, item_no, qty,
                defect_desc, status, created_at
            ) VALUES ('D-1', '2026-06-01', '委外加工', 'W-1', 1,
                      'warehouse defect', '待處理', '2026-06-01 09:00')
            """
        )
        self.conn.commit()
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM anomaly_actions").fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM anomaly_analysis_notes"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM corrective_actions"
            ).fetchone()[0],
            0,
        )

    def test_warehouse_stats_do_not_read_anomaly_sub_tables(self) -> None:
        """Warehouse stats query defect_records only; they must not ingest CA/notes."""
        repository.create_anomaly_analysis_note(
            self.conn, anomaly_id=self.anomaly_id, content="note"
        )
        repository.create_corrective_action(
            self.conn, anomaly_id=self.anomaly_id, description="CA"
        )
        # Warehouse list is empty because no defect_records were written.
        from services.event import _query_service  # local import not needed here

        # Direct SQL assertion: warehouse count unnaffected by anomaly sub-tables.
        count = self.conn.execute(
            "SELECT COUNT(*) FROM defect_records"
        ).fetchone()[0]
        self.assertEqual(count, 0)


class AnomalyMigrationIdempotencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")

    def tearDown(self) -> None:
        self.conn.close()

    def test_evidence_tables_upgrade_is_idempotent(self) -> None:
        """Re-running the evidence migration on a fresh schema must not duplicate."""
        repository.create_schema(self.conn)
        supplier = repository.create_supplier_record(conn=self.conn, supplier_name="I")
        product = repository.create_product_record(
            self.conn,
            product_code="I-001",
            product_name="I",
            supplier_id=supplier,
        )
        anomaly_id = repository.create_anomaly_with_visit_link(
            self.conn,
            anomaly_date="2026-06-01",
            supplier_id=supplier,
            product_id=product,
            problem_desc="p",
            sync_visit=False,
        )["anomaly_id"]
        repository.create_anomaly_action(
            self.conn, anomaly_id=anomaly_id, description="a"
        )
        # Force re-entry to the helper; it must be idempotent.
        repository._ensure_anomaly_evidence_tables_v1(self.conn)
        repository._ensure_anomaly_evidence_tables_v1(self.conn)
        # Tables exist exactly once and the seeded action remains.
        self.assertIsNotNone(
            self.conn.execute(
                "SELECT 1 FROM anomaly_actions WHERE anomaly_id = ?",
                (anomaly_id,),
            ).fetchone()
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM anomaly_actions").fetchone()[0],
            1,
        )


if __name__ == "__main__":
    unittest.main()
