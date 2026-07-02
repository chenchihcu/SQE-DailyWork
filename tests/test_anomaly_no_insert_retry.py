from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from database import repository


class InsertAnomalyRowRetryTests(unittest.TestCase):
    """Covers audit finding A7: _insert_anomaly_row must retry anomaly_no
    generation on a UNIQUE collision (mirroring _apply_key_updates' existing
    retry pattern) instead of letting sqlite3.IntegrityError propagate on the
    create_anomaly direct-insert path."""

    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_insert_retry_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.supplier_id = repository.create_supplier_record(
            self.conn, supplier_name="Retry Supplier"
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_create_anomaly_retries_past_collision_and_succeeds(self) -> None:
        # Pre-occupy the number _next_anomaly_no would naturally hand out
        # first, forcing the retry path to kick in.
        repository._insert_anomaly_row(
            self.conn,
            anomaly_date="2026-07-01",
            supplier_id=self.supplier_id,
            problem_desc="occupies 20260701001",
        )
        self.conn.commit()

        call_count = 0
        real_next = repository._next_anomaly_no

        def _colliding_then_real(conn, anomaly_date):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "20260701001"  # collides with the row inserted above
            return real_next(conn, anomaly_date)

        with patch.object(repository, "_next_anomaly_no", side_effect=_colliding_then_real):
            anomaly_no = repository.create_anomaly(
                self.conn,
                anomaly_date="2026-07-01",
                supplier_id=self.supplier_id,
                problem_desc="second anomaly",
            )

        self.assertEqual("20260701002", anomaly_no)
        self.assertEqual(2, call_count)
        rows = self.conn.execute(
            "SELECT anomaly_no FROM anomalies ORDER BY anomaly_no"
        ).fetchall()
        self.assertEqual(
            ["20260701001", "20260701002"],
            [str(row["anomaly_no"]) for row in rows],
        )

    def test_create_anomaly_gives_up_after_max_retries(self) -> None:
        repository._insert_anomaly_row(
            self.conn,
            anomaly_date="2026-07-01",
            supplier_id=self.supplier_id,
            problem_desc="occupies 20260701001",
        )
        self.conn.commit()

        call_count = 0

        def _always_colliding(conn, anomaly_date):
            nonlocal call_count
            call_count += 1
            return "20260701001"

        with patch.object(repository, "_next_anomaly_no", side_effect=_always_colliding):
            with self.assertRaises(sqlite3.IntegrityError):
                repository.create_anomaly(
                    self.conn,
                    anomaly_date="2026-07-01",
                    supplier_id=self.supplier_id,
                    problem_desc="always collides",
                )

        self.assertEqual(3, call_count)

    def test_explicit_anomaly_no_does_not_retry_on_collision(self) -> None:
        # create_anomaly_with_visit_link's path: anomaly_no is pre-reserved
        # and already embedded in other text, so a collision must propagate
        # rather than silently regenerate a different number.
        repository._insert_anomaly_row(
            self.conn,
            anomaly_date="2026-07-01",
            supplier_id=self.supplier_id,
            problem_desc="occupies fixed number",
            anomaly_no="FIXED-001",
        )
        self.conn.commit()

        with self.assertRaises(sqlite3.IntegrityError):
            repository._insert_anomaly_row(
                self.conn,
                anomaly_date="2026-07-01",
                supplier_id=self.supplier_id,
                problem_desc="duplicate fixed number",
                anomaly_no="FIXED-001",
            )


if __name__ == "__main__":
    unittest.main()
