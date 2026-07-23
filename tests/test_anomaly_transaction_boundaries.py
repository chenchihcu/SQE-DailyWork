from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from database import repository
from services.event import _anomaly_service


class AnomalyTransactionBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.supplier_id = repository.create_supplier_record(
            self.conn, supplier_name="交易測試供應商"
        )
        self.product_id = repository.create_product_record(
            self.conn,
            product_code="TX-001",
            product_name="交易測試產品",
            supplier_id=self.supplier_id,
        )

    def tearDown(self) -> None:
        self.conn.close()

    def _anomaly_id(self, anomaly_no: str) -> str:
        return str(
            self.conn.execute(
                "SELECT id FROM anomalies WHERE anomaly_no = ?", (anomaly_no,)
            ).fetchone()[0]
        )

    def test_create_rolls_back_when_cache_refresh_fails(self) -> None:
        with patch.object(
            repository,
            "refresh_monthly_cache",
            side_effect=RuntimeError("cache failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "cache failure"):
                repository.create_anomaly(
                    self.conn,
                    anomaly_date="2026-06-01",
                    supplier_id=self.supplier_id,
                    product_id=self.product_id,
                    problem_desc="must roll back",
                )
        self.assertEqual(0, self.conn.execute("SELECT COUNT(*) FROM anomalies").fetchone()[0])

    def test_update_rolls_back_when_cache_refresh_fails(self) -> None:
        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-06-01",
            supplier_id=self.supplier_id,
            product_id=self.product_id,
            problem_desc="before",
        )
        anomaly_id = self._anomaly_id(anomaly_no)
        with patch.object(
            repository,
            "refresh_monthly_cache",
            side_effect=RuntimeError("cache failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "cache failure"):
                repository.update_anomaly(
                    self.conn,
                    anomaly_id=anomaly_id,
                    anomaly_no="20260602001",
                    anomaly_date="2026-06-02",
                    supplier_id=self.supplier_id,
                    product_id=self.product_id,
                    problem_desc="after",
                )
        detail = repository.get_anomaly_detail(self.conn, anomaly_id)
        self.assertEqual("before", detail["problem_desc"])
        self.assertEqual("2026-06-01", detail["anomaly_date"])

    def test_close_rolls_back_when_cache_refresh_fails(self) -> None:
        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date="2026-06-01",
            supplier_id=self.supplier_id,
            product_id=self.product_id,
            problem_desc="open",
        )
        anomaly_id = self._anomaly_id(anomaly_no)
        with patch.object(
            repository,
            "refresh_monthly_cache",
            side_effect=RuntimeError("cache failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "cache failure"):
                repository.close_anomaly(
                    self.conn,
                    anomaly_id,
                    "improved",
                    closed_at="2026-06-02",
                )
        detail = repository.get_anomaly_detail(self.conn, anomaly_id)
        self.assertEqual("待處理", detail["status"])
        self.assertIsNone(detail["closed_at"])

    def test_linked_create_rolls_back_visit_and_anomaly_on_cache_failure(self) -> None:
        with patch.object(
            repository,
            "refresh_monthly_cache",
            side_effect=RuntimeError("cache failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "cache failure"):
                repository.create_anomaly_with_visit_link(
                    self.conn,
                    anomaly_date="2026-06-01",
                    supplier_id=self.supplier_id,
                    product_id=self.product_id,
                    problem_desc="linked",
                    sync_visit=True,
                )
        self.assertEqual(0, self.conn.execute("SELECT COUNT(*) FROM anomalies").fetchone()[0])
        self.assertEqual(0, self.conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0])

    def test_snapshot_failure_returns_warning_without_rolling_back_database(self) -> None:
        with (
            patch("database.connection.get_connection", return_value=self.conn),
            patch.object(
                _anomaly_service,
                "write_anomaly_markdown",
                side_effect=OSError("snapshot unavailable"),
            ),
        ):
            result = _anomaly_service.create_anomaly_with_visit_link(
                {
                    "anomaly_date": "2026-06-01",
                    "supplier_id": self.supplier_id,
                    "product_id": self.product_id,
                    "problem_desc": "database succeeds",
                    "sync_visit": False,
                }
            )
        self.assertTrue(result["warnings"])
        self.assertIn("請勿重複", result["warnings"][0])
        self.assertEqual(1, self.conn.execute("SELECT COUNT(*) FROM anomalies").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
