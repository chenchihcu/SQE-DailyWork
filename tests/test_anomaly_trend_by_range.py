from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from database import repository
from services import event_service


class AnomalyTrendByRangeTests(unittest.TestCase):
    """Covers audit finding E1: get_anomaly_trend_by_range was rewritten
    from up-to-48 per-month SQL queries into 3 grouped queries. This test
    hand-derives expected values for a dataset that exercises every branch
    of the original logic (same-month close, cross-month close, always-open
    overdue, never-overdue-because-empty-due-date, and the backlog
    cutoff-per-month condition) so a regression in the rewrite is caught
    even without a literal old-vs-new comparison."""

    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_anomaly_trend_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.supplier_id = repository.create_supplier_record(
            self.conn, supplier_name="Trend Supplier"
        )

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _create_anomaly(self, anomaly_date: str) -> str:
        return repository.create_anomaly(
            self.conn,
            anomaly_date=anomaly_date,
            supplier_id=self.supplier_id,
            problem_desc=f"Problem at {anomaly_date}",
        )

    def _force_close(self, anomaly_no: str, closed_at: str) -> None:
        self.conn.execute(
            "UPDATE anomalies SET status = '已結案', closed_at = ? WHERE anomaly_no = ?",
            (closed_at, anomaly_no),
        )
        self.conn.commit()

    def _find_anomaly_id(self, anomaly_no: str) -> str:
        row = self.conn.execute(
            "SELECT id FROM anomalies WHERE anomaly_no = ?",
            (anomaly_no,),
        ).fetchone()
        assert row is not None
        return str(row["id"])

    def _set_due_date(self, anomaly_no: str, due_date: str) -> None:
        self.conn.execute(
            "UPDATE anomalies SET due_date = ? WHERE anomaly_no = ?",
            (due_date, anomaly_no),
        )
        self.conn.commit()

    def test_trend_matches_hand_derived_expectations(self) -> None:
        # A: opened Jan, closed in Feb (cross-month close).
        a = self._create_anomaly("2026-01-05")
        self._force_close(a, "2026-02-10")

        # B: opened Jan, never closed, due date far in the past -> always
        # overdue regardless of when this test runs.
        b = self._create_anomaly("2026-01-10")
        self._set_due_date(b, "2020-01-01")

        # C: opened Feb, never closed, no due date set -> open but not
        # overdue (the '待處理' status alone doesn't make it overdue).
        self._create_anomaly("2026-02-15")

        # D: opened March, closed same month.
        d = self._create_anomaly("2026-03-01")
        self._force_close(d, "2026-03-05")

        with patch("database.connection.get_connection", return_value=self.conn):
            trend = event_service.get_anomaly_trend_by_range("2026-01-01", "2026-03-31")

        by_month = {row["yyyymm"]: row for row in trend}
        self.assertEqual(["2026-01", "2026-02", "2026-03"], [row["yyyymm"] for row in trend])

        self.assertEqual(2, by_month["2026-01"]["total_count"])
        self.assertEqual(1, by_month["2026-02"]["total_count"])
        self.assertEqual(1, by_month["2026-03"]["total_count"])

        # closed_count is grouped by closed_at's month, not anomaly_date's.
        self.assertEqual(0, by_month["2026-01"]["closed_count"])
        self.assertEqual(1, by_month["2026-02"]["closed_count"])
        self.assertEqual(1, by_month["2026-03"]["closed_count"])

        # overdue_count: only B (待處理 + due_date far in the past).
        self.assertEqual(1, by_month["2026-01"]["overdue_count"])
        self.assertEqual(0, by_month["2026-02"]["overdue_count"])
        self.assertEqual(0, by_month["2026-03"]["overdue_count"])

        # backlog_count: A counts as open through Jan (closed_at month
        # 2026-02 > 2026-01), stops counting from Feb onward. B counts every
        # month (never closed). C counts from Feb onward. D never counts
        # (closed the same month it was opened).
        self.assertEqual(2, by_month["2026-01"]["backlog_count"])  # A, B
        self.assertEqual(2, by_month["2026-02"]["backlog_count"])  # B, C
        self.assertEqual(2, by_month["2026-03"]["backlog_count"])  # B, C

    def test_empty_range_returns_zero_rows_for_untouched_months(self) -> None:
        with patch("database.connection.get_connection", return_value=self.conn):
            trend = event_service.get_anomaly_trend_by_range("2026-05-01", "2026-05-31")

        self.assertEqual(1, len(trend))
        row = trend[0]
        self.assertEqual("2026-05", row["yyyymm"])
        self.assertEqual(0, row["total_count"])
        self.assertEqual(0, row["closed_count"])
        self.assertEqual(0, row["overdue_count"])
        self.assertEqual(0, row["backlog_count"])

    def test_closed_count_follows_user_selected_closed_date_after_edit(self) -> None:
        anomaly_no = self._create_anomaly("2026-01-10")
        anomaly_id = self._find_anomaly_id(anomaly_no)
        repository.close_anomaly(
            self.conn,
            anomaly_id=anomaly_id,
            improvement_desc="fixed",
            closed_at="2026-03-05",
        )

        with patch("database.connection.get_connection", return_value=self.conn):
            initial = event_service.get_anomaly_trend_by_range("2026-01-01", "2026-04-30")

        initial_by_month = {row["yyyymm"]: row for row in initial}
        self.assertEqual(1, initial_by_month["2026-03"]["closed_count"])
        self.assertEqual(0, initial_by_month["2026-04"]["closed_count"])

        repository.update_anomaly_closed_at(
            self.conn,
            anomaly_id=anomaly_id,
            closed_at="2026-04-10",
        )

        with patch("database.connection.get_connection", return_value=self.conn):
            updated = event_service.get_anomaly_trend_by_range("2026-01-01", "2026-04-30")

        updated_by_month = {row["yyyymm"]: row for row in updated}
        self.assertEqual(0, updated_by_month["2026-03"]["closed_count"])
        self.assertEqual(1, updated_by_month["2026-04"]["closed_count"])

    def test_partial_month_range_filters_event_counts_by_exact_dates(self) -> None:
        self._create_anomaly("2026-06-01")
        self._create_anomaly("2026-06-15")
        self._create_anomaly("2026-06-30")

        with patch("database.connection.get_connection", return_value=self.conn):
            trend = event_service.get_anomaly_trend_by_range("2026-06-10", "2026-06-20")

        self.assertEqual(1, len(trend))
        row = trend[0]
        self.assertEqual("2026-06", row["yyyymm"])
        self.assertEqual(1, row["total_count"])
        # Backlog is a stock metric as of the range cutoff: include already-open
        # prior work, but do not include future same-month rows after end_date.
        self.assertEqual(2, row["backlog_count"])

    def test_partial_month_visit_trend_filters_visits_and_visit_anomalies_by_exact_dates(self) -> None:
        outside_visit = repository.create_visit(
            self.conn,
            visit_date="2026-06-01",
            supplier_id=self.supplier_id,
            summary="outside start",
        )
        inside_visit = repository.create_visit(
            self.conn,
            visit_date="2026-06-15",
            supplier_id=self.supplier_id,
            summary="inside",
        )
        future_visit = repository.create_visit(
            self.conn,
            visit_date="2026-06-30",
            supplier_id=self.supplier_id,
            summary="outside end",
        )
        repository.create_anomaly(
            self.conn,
            anomaly_date="2026-06-01",
            supplier_id=self.supplier_id,
            problem_desc="outside linked anomaly",
            visit_id=outside_visit,
        )
        repository.create_anomaly(
            self.conn,
            anomaly_date="2026-06-15",
            supplier_id=self.supplier_id,
            problem_desc="inside linked anomaly",
            visit_id=inside_visit,
        )
        repository.create_anomaly(
            self.conn,
            anomaly_date="2026-06-30",
            supplier_id=self.supplier_id,
            problem_desc="future linked anomaly",
            visit_id=future_visit,
        )

        with patch("database.connection.get_connection", return_value=self.conn):
            trend = event_service.get_visit_trend_by_range("2026-06-10", "2026-06-20")

        self.assertEqual(
            [{"yyyymm": "2026-06", "visit_count": 1, "visit_anomaly_count": 1}],
            trend,
        )

    def test_invalid_date_range_returns_empty_list(self) -> None:
        with patch("database.connection.get_connection", return_value=self.conn):
            trend = event_service.get_anomaly_trend_by_range("not-a-date", "also-not-a-date")
        self.assertEqual([], trend)


if __name__ == "__main__":
    unittest.main()
