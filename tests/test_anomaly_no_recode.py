from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from uuid import uuid4

from database import repository


class AnomalyNoRecodeTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_recode_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.supplier_id = repository.create_supplier_record(
            self.conn, supplier_name="Recode Supplier"
        )

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _insert_anomaly(
        self,
        *,
        anomaly_no: str,
        anomaly_date: str,
        created_at: str,
        problem_desc: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO anomalies(
                id, anomaly_no, anomaly_date, supplier_id, problem_desc,
                status, improvement_desc, closed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, '待處理', '', NULL, ?, ?)
            """,
            (
                uuid4().hex,
                anomaly_no,
                anomaly_date,
                self.supplier_id,
                problem_desc,
                created_at,
                created_at,
            ),
        )

    def _insert_visit(self, *, summary: str, created_at: str) -> None:
        self.conn.execute(
            """
            INSERT INTO visits(
                id, visit_date, supplier_id, summary, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, '已完成', ?, ?)
            """,
            (
                uuid4().hex,
                "2026-04-15",
                self.supplier_id,
                summary,
                created_at,
                created_at,
            ),
        )

    def test_recode_updates_key_and_text_columns(self) -> None:
        self._insert_anomaly(
            anomaly_no="ANM-20260415-001",
            anomaly_date="2026-04-15",
            created_at="2026-04-15 10:00:00",
            problem_desc="legacy 1",
        )
        self._insert_anomaly(
            anomaly_no="2026年04月15日 -SN 001",
            anomaly_date="2026-04-15",
            created_at="2026-04-15 10:05:00",
            problem_desc="legacy 2",
        )
        self._insert_anomaly(
            anomaly_no="ANM-20260415-002",
            anomaly_date="2026-04-15",
            created_at="2026-04-15 10:10:00",
            problem_desc="legacy 3",
        )
        self._insert_visit(
            summary="由異常單 ANM-20260415-001 / 2026年04月15日 -SN 001 同步建立訪廠紀錄。",
            created_at="2026-04-15 10:15:00",
        )
        self.conn.commit()

        report = repository.recode_anomaly_numbers(
            self.conn,
            apply=True,
            rewrite_text=True,
            migration_meta_key=None,
        )

        rows = self.conn.execute(
            """
            SELECT anomaly_no
            FROM anomalies
            ORDER BY anomaly_date, created_at, rowid
            """
        ).fetchall()
        self.assertEqual(
            ["20260415001", "20260415002", "20260415003"],
            [str(row["anomaly_no"]) for row in rows],
        )

        visit_row = self.conn.execute(
            "SELECT summary FROM visits ORDER BY created_at LIMIT 1"
        ).fetchone()
        self.assertIsNotNone(visit_row)
        assert visit_row is not None
        self.assertIn("20260415001", str(visit_row["summary"]))
        self.assertIn("20260415002", str(visit_row["summary"]))
        self.assertNotIn("ANM-20260415-001", str(visit_row["summary"]))
        self.assertNotIn("2026年04月15日 -SN 001", str(visit_row["summary"]))

        self.assertTrue(report["applied"])
        self.assertEqual(3, report["key_changes"])
        self.assertGreaterEqual(report["text_changes"], 1)
        self.assertEqual(3, report["table_reports"]["anomalies"]["key_changes"])

    def test_recode_dry_run_keeps_original_values(self) -> None:
        self._insert_anomaly(
            anomaly_no="ANM-20260415-001",
            anomaly_date="2026-04-15",
            created_at="2026-04-15 10:00:00",
            problem_desc="dry-run",
        )
        self.conn.commit()

        report = repository.recode_anomaly_numbers(
            self.conn,
            apply=False,
            rewrite_text=True,
            migration_meta_key=None,
        )
        row = self.conn.execute(
            "SELECT anomaly_no FROM anomalies ORDER BY created_at LIMIT 1"
        ).fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual("ANM-20260415-001", str(row["anomaly_no"]))
        self.assertEqual("dry_run", report["reason"])
        self.assertEqual(1, report["key_changes"])

    def test_recode_handles_unique_swap_without_conflict(self) -> None:
        self._insert_anomaly(
            anomaly_no="20260415002",
            anomaly_date="2026-04-15",
            created_at="2026-04-15 10:00:00",
            problem_desc="swap-1",
        )
        self._insert_anomaly(
            anomaly_no="20260415001",
            anomaly_date="2026-04-15",
            created_at="2026-04-15 10:05:00",
            problem_desc="swap-2",
        )
        self.conn.commit()

        repository.recode_anomaly_numbers(
            self.conn,
            apply=True,
            rewrite_text=False,
            migration_meta_key=None,
        )
        rows = self.conn.execute(
            """
            SELECT anomaly_no
            FROM anomalies
            ORDER BY created_at, rowid
            """
        ).fetchall()
        self.assertEqual(
            ["20260415001", "20260415002"],
            [str(row["anomaly_no"]) for row in rows],
        )


if __name__ == "__main__":
    unittest.main()
