from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from unittest import mock
from uuid import uuid4

from database import repository
from services import event_service


class ProcessKeywordParetoTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_process_keyword_pareto_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.supplier_id = repository.create_supplier_record(
            self.conn, supplier_name="Keyword Supplier"
        )

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _create(self, anomaly_date: str, keywords: str) -> None:
        repository.create_anomaly(
            self.conn,
            anomaly_date=anomaly_date,
            supplier_id=self.supplier_id,
            problem_desc=f"Problem {keywords or 'blank'}",
            process_keywords=keywords,
        )

    def test_multi_tag_counts_each_keyword(self) -> None:
        self._create("2026-03-01", "SPI\n回流焊")
        self._create("2026-03-02", "SPI\n空焊")

        with mock.patch("database.connection.get_connection", return_value=self.conn):
            rows = event_service.get_anomaly_process_keyword_pareto_by_range(
                "2026-03-01", "2026-03-31"
            )

        self.assertEqual(
            [
                {"rank": 1, "keyword": "SPI", "count": 2, "percent": 50.0, "cumulative_percent": 50.0},
                {"rank": 2, "keyword": "回流焊", "count": 1, "percent": 25.0, "cumulative_percent": 75.0},
                {"rank": 3, "keyword": "空焊", "count": 1, "percent": 25.0, "cumulative_percent": 100.0},
            ],
            rows,
        )

    def test_empty_keywords_are_excluded(self) -> None:
        self._create("2026-03-03", "")
        self._create("2026-03-04", "SPI")

        with mock.patch("database.connection.get_connection", return_value=self.conn):
            rows = event_service.get_anomaly_process_keyword_pareto_by_range(
                "2026-03-01", "2026-03-31"
            )

        self.assertEqual([{"rank": 1, "keyword": "SPI", "count": 1, "percent": 100.0, "cumulative_percent": 100.0}], rows)


if __name__ == "__main__":
    unittest.main()
