from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from database import repository
from database.product_stage import (
    PRODUCT_STAGE_MASS_PRODUCTION,
    PRODUCT_STAGE_TRIAL_PRODUCTION,
)
from services import event_service


class AnomalyProductStageStatsTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_product_stage_{uuid4().hex}.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.supplier_id = repository.create_supplier_record(
            self.conn, supplier_name="Product Stage Supplier"
        )

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _create_anomaly(self, anomaly_date: str, *, product_stage: str) -> None:
        anomaly_no = repository.create_anomaly(
            self.conn,
            anomaly_date=anomaly_date,
            supplier_id=self.supplier_id,
            problem_desc="Stage test",
            category="外觀",
        )
        normalized_stage = (
            PRODUCT_STAGE_TRIAL_PRODUCTION
            if str(product_stage or "").strip() == PRODUCT_STAGE_TRIAL_PRODUCTION
            else PRODUCT_STAGE_MASS_PRODUCTION
        )
        self.conn.execute(
            "UPDATE anomalies SET product_stage = ? WHERE anomaly_no = ?",
            (normalized_stage, anomaly_no),
        )
        self.conn.commit()

    def test_product_stage_distribution_normalizes_and_orders_rows(self) -> None:
        self._create_anomaly("2026-04-01", product_stage=PRODUCT_STAGE_MASS_PRODUCTION)
        self._create_anomaly("2026-04-02", product_stage=PRODUCT_STAGE_MASS_PRODUCTION)
        self._create_anomaly("2026-04-03", product_stage=PRODUCT_STAGE_TRIAL_PRODUCTION)
        self._create_anomaly("2026-04-04", product_stage="")

        with patch("database.connection.get_connection", return_value=self.conn):
            rows = event_service.get_anomaly_product_stage_distribution_by_range(
                "2026-04-01", "2026-04-30"
            )

        self.assertEqual(
            [
                {
                    "product_stage": PRODUCT_STAGE_MASS_PRODUCTION,
                    "count": 3,
                    "percent": 75.0,
                },
                {
                    "product_stage": PRODUCT_STAGE_TRIAL_PRODUCTION,
                    "count": 1,
                    "percent": 25.0,
                },
            ],
            rows,
        )

    def test_product_stage_distribution_returns_empty_for_blank_range(self) -> None:
        with patch("database.connection.get_connection", return_value=self.conn):
            rows = event_service.get_anomaly_product_stage_distribution_by_range(
                "2026-04-01", "2026-04-30"
            )

        self.assertEqual([], rows)


if __name__ == "__main__":
    unittest.main()
