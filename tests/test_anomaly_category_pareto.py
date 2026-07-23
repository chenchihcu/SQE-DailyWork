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

    def _create_anomaly(
        self, anomaly_date: str, category: str
    ) -> str:
        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date=anomaly_date,
            supplier_id=self.supplier_id,
            problem_desc=f"Problem {category or 'blank'}",
            category=category,
        )
        return anomaly_no

    def test_category_pareto_normalizes_sorts_and_calculates_percentages(self) -> None:
        self._create_anomaly("2026-01-05", "B類")
        self._create_anomaly("2026-01-06", "B類")
        self._create_anomaly("2026-01-07", "A類")
        self._create_anomaly("2026-01-08", "A類")
        self._create_anomaly("2026-01-09", "")
        self._create_anomaly("2026-02-01", "根因A")

        with patch("database.connection.get_connection", return_value=self.conn):
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

    def test_category_pareto_falls_back_on_blank(self) -> None:
        self._create_anomaly("2026-01-05", "來料品質不良")
        self._create_anomaly("2026-01-06", "製程參數失控")
        self._create_anomaly("2026-01-07", "")

        with patch("database.connection.get_connection", return_value=self.conn):
            rows = event_service.get_anomaly_category_pareto_by_range(
                "2026-01-01", "2026-01-31"
            )

        self.assertEqual(
            [
                {"rank": 1, "category": "來料品質不良", "count": 1, "percent": 33.3, "cumulative_percent": 33.3},
                {"rank": 2, "category": "製程參數失控", "count": 1, "percent": 33.3, "cumulative_percent": 66.7},
                {"rank": 3, "category": "未分類", "count": 1, "percent": 33.3, "cumulative_percent": 100.0},
            ],
            rows,
        )

    def test_category_pareto_accumulates_when_normalization_merges_sql_groups(self) -> None:
        # SQL TRIM 只去 ASCII 空白;「其他」與「其他+全形空白」在 SQL 分成兩組,
        # Python 正規化後歸同一鍵 — 計數必須累加,不能覆蓋掉數。
        self._create_anomaly("2026-01-05", "其他")
        self._create_anomaly("2026-01-06", "其他　")
        self._create_anomaly("2026-01-07", "來料品質不良")

        with patch("database.connection.get_connection", return_value=self.conn):
            rows = event_service.get_anomaly_category_pareto_by_range(
                "2026-01-01", "2026-01-31"
            )

        by_category = {row["category"]: row["count"] for row in rows}
        self.assertEqual(2, by_category.get("其他"))
        self.assertEqual(1, by_category.get("來料品質不良"))
        self.assertEqual(3, sum(by_category.values()))

    def test_list_events_by_range_resolves_category_like_page_lists(self) -> None:
        self._create_anomaly("2026-01-05", "製程參數失控")
        self._create_anomaly("2026-01-06", "規範文件缺漏")

        with patch("database.connection.get_connection", return_value=self.conn):
            events = event_service.list_events_by_range("2026-01-01", "2026-01-31")

        by_date = {e["event_date"]: e for e in events}
        self.assertEqual("製程參數失控", by_date["2026-01-05"]["category"])
        self.assertEqual("規範文件缺漏", by_date["2026-01-06"]["category"])


if __name__ == "__main__":
    unittest.main()
