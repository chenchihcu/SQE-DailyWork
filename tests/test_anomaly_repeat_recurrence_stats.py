from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from database import repository
from database.repo_helpers import _gen_id
from services import event_service
from services.event._query_service import (
    REPEAT_RECURRENCE_BUCKET_FIRST_TIME,
    REPEAT_RECURRENCE_BUCKET_FLAGGED,
)


class AnomalyRepeatRecurrenceStatsTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_repeat_recurrence_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.supplier_id = repository.create_supplier_record(
            self.conn, supplier_name="Repeat Recurrence Supplier"
        )

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _create_anomaly(self, anomaly_date: str, *, suffix: str) -> str:
        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date=anomaly_date,
            supplier_id=self.supplier_id,
            problem_desc=f"Problem {suffix}",
            category="外觀",
        )
        row = self.conn.execute(
            "SELECT id FROM anomalies WHERE anomaly_no = ?",
            (anomaly_no,),
        ).fetchone()
        return str(row["id"])

    def _insert_repeat_link(self, anomaly_id: str, peer_anomaly_id: str) -> None:
        self.conn.execute(
            """
            INSERT INTO anomaly_repeat_links(
                id, anomaly_id, peer_anomaly_id, similarity_score, match_reasons
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (_gen_id(), anomaly_id, peer_anomaly_id, 80, "test"),
        )
        self.conn.commit()

    def test_repeat_recurrence_counts_flagged_and_first_time(self) -> None:
        first_id = self._create_anomaly("2026-03-01", suffix="a")
        flagged_id = self._create_anomaly("2026-03-02", suffix="b")
        peer_id = self._create_anomaly("2026-02-01", suffix="peer")
        self._insert_repeat_link(flagged_id, peer_id)

        with patch("database.connection.get_connection", return_value=self.conn):
            rows = event_service.get_anomaly_repeat_recurrence_by_range(
                "2026-03-01", "2026-03-31"
            )

        self.assertEqual(
            [
                {
                    "bucket": REPEAT_RECURRENCE_BUCKET_FLAGGED,
                    "count": 1,
                    "percent": 50.0,
                },
                {
                    "bucket": REPEAT_RECURRENCE_BUCKET_FIRST_TIME,
                    "count": 1,
                    "percent": 50.0,
                },
            ],
            rows,
        )

    def test_repeat_recurrence_excludes_out_of_range_cases(self) -> None:
        out_of_range_id = self._create_anomaly("2026-02-15", suffix="old")
        peer_id = self._create_anomaly("2026-01-10", suffix="peer")
        self._insert_repeat_link(out_of_range_id, peer_id)

        with patch("database.connection.get_connection", return_value=self.conn):
            rows = event_service.get_anomaly_repeat_recurrence_by_range(
                "2026-03-01", "2026-03-31"
            )

        self.assertEqual([], rows)

    def test_repeat_recurrence_returns_empty_when_table_missing(self) -> None:
        self._create_anomaly("2026-03-01", suffix="only")
        self.conn.execute("DROP TABLE IF EXISTS anomaly_repeat_links")
        self.conn.commit()

        with patch("database.connection.get_connection", return_value=self.conn):
            rows = event_service.get_anomaly_repeat_recurrence_by_range(
                "2026-03-01", "2026-03-31"
            )

        self.assertEqual([], rows)


if __name__ == "__main__":
    unittest.main()
