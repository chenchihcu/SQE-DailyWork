from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from database.repository import create_schema
from services import supplier_360_service


class SupplierScorecardTests(unittest.TestCase):
    def test_grade_threshold_boundaries(self) -> None:
        self.assertEqual(
            "A",
            supplier_360_service._grade_from_metrics(0.9, 2),
        )
        self.assertEqual(
            "B",
            supplier_360_service._grade_from_metrics(0.75, 5),
        )
        self.assertEqual(
            "C",
            supplier_360_service._grade_from_metrics(0.5, 6),
        )

    def test_scorecard_uses_grade_helper(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        create_schema(conn)
        conn.execute(
            """
            INSERT INTO suppliers(
                id, supplier_name, contact_name, department, phone,
                contact_email, category, is_active
            ) VALUES ('sup-1', '評級供應商', '', '', '', '', '正式供應商', 1)
            """
        )
        conn.execute(
            """
            INSERT INTO anomalies(
                id, anomaly_no, anomaly_date, supplier_id, problem_desc,
                status, due_date, closed_at
            ) VALUES (
                'a-1', '20260801001', '2026-08-01', 'sup-1', '問題',
                '已結案', '2026-08-10', '2026-08-05'
            )
            """
        )
        conn.commit()
        with patch.object(
            supplier_360_service._connection,
            "get_connection",
            return_value=conn,
        ):
            scorecard = supplier_360_service.get_supplier_scorecard(
                "sup-1", "2026-08-01", "2026-08-31"
            )
        self.assertEqual("A", scorecard["grade"])
        self.assertEqual(1, scorecard["anomaly_count"])


if __name__ == "__main__":
    unittest.main()
