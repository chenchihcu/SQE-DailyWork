from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from database import repository
from services import event_service


class AnomalyCategoryParetoTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_category_pareto_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.supplier_id = repository.create_supplier_record(
            self.conn, supplier_name="Pareto Supplier"
        )

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _create_anomaly(self, anomaly_date: str, category: str) -> None:
        repository.create_anomaly(
            self.conn,
            anomaly_date=anomaly_date,
            supplier_id=self.supplier_id,
            problem_desc=f"Problem {category or 'blank'}",
            category=category,
        )

    def test_category_pareto_normalizes_sorts_and_calculates_percentages(self) -> None:
        self._create_anomaly("2026-01-05", "B類")
        self._create_anomaly("2026-01-06", "B類")
        self._create_anomaly("2026-01-07", "A類")
        self._create_anomaly("2026-01-08", "A類")
        self._create_anomaly("2026-01-09", "")
        self._create_anomaly("2026-02-01", "根因A")

        with patch.object(event_service, "get_connection", return_value=self.conn):
            rows = event_service.get_anomaly_category_pareto_by_range(
                "2026-01-01", "2026-01-31"
            )

        self.assertEqual(
            [
                {"rank": 1, "category": "A類", "count": 2, "percent": 40.0, "cumulative_percent": 40.0},
                {"rank": 2, "category": "B類", "count": 2, "percent": 40.0, "cumulative_percent": 80.0},
                {"rank": 3, "category": "未分類", "count": 1, "percent": 20.0, "cumulative_percent": 100.0},
            ],
            rows,
        )

    def test_category_pareto_prefers_root_cause_and_ignores_visits_when_summarizing_events(self) -> None:
        rows = event_service.summarize_anomaly_category_pareto([
            {
                "event_type": "ANOMALY",
                "category": "來料品質不良",
                "root_cause_category": "物料/來料品質異常",
            },
            {"event_type": "ANOMALY", "category": ""},
            {"event_type": "VISIT", "category": "來料品質不良"},
        ])

        self.assertEqual(
            [
                {"rank": 1, "category": "物料/來料品質異常", "count": 1, "percent": 50.0, "cumulative_percent": 50.0},
                {"rank": 2, "category": "未分類", "count": 1, "percent": 50.0, "cumulative_percent": 100.0},
            ],
            rows,
        )


if __name__ == "__main__":
    unittest.main()
