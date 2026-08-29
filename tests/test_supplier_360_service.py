from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from database.repository import create_schema
from services import supplier_360_service
from database import case_action_repository


class Supplier360ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        create_schema(self.conn)
        self.conn.executemany(
            """
            INSERT INTO suppliers(
                id, supplier_name, contact_name, department, phone,
                contact_email, category, is_active
            ) VALUES (?, ?, '', '', '', '', '正式供應商', ?)
            """,
            [
                ("open", "有未結異常", 1),
                ("closed", "僅已結案異常", 1),
                ("clean", "沒有異常", 1),
                ("inactive", "停用供應商", 0),
            ],
        )
        self.conn.execute(
            """
            INSERT INTO anomalies(
                id, anomaly_no, anomaly_date, supplier_id, problem_desc,
                status, due_date
            ) VALUES
                ('a-open', '20260820001', '2026-08-20', 'open', '未結問題',
                 '待處理', '2026-08-19'),
                ('a-closed', '20260820002', '2026-08-20', 'closed', '已結問題',
                 '已結案', '2026-08-19')
            """
        )
        self.conn.execute(
            """
            INSERT INTO visits(id, visit_date, supplier_id, summary)
            VALUES ('v-open', '2026-08-18', 'open', '最近訪廠')
            """
        )
        case_action_repository.create_case_action(
            self.conn,
            anomaly_id="a-open",
            action_type="NEXT_ACTION",
            description="overdue action",
            due_date="2026-08-19",
            execution_status="執行中",
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def _rows(self, scope: str) -> dict[str, dict]:
        with patch.object(
            supplier_360_service._connection,
            "get_connection",
            return_value=self.conn,
        ):
            return {
                row["id"]: row
                for row in supplier_360_service.list_supplier_rows(view_scope=scope)
            }

    def test_default_scope_returns_only_suppliers_with_open_anomalies(self) -> None:
        rows = self._rows("open_anomaly")
        self.assertEqual({"open"}, set(rows))
        self.assertEqual(1, rows["open"]["open_anomaly_count"])
        self.assertEqual(1, rows["open"]["overdue_anomaly_count"])
        self.assertEqual("2026-08-18", rows["open"]["latest_visit_date"])
        self.assertEqual("20260820001", rows["open"]["latest_anomaly_no"])
        self.assertEqual("未結問題", rows["open"]["latest_anomaly_desc"])
        self.assertEqual("2026-08-19", rows["open"]["latest_anomaly_due_date"])

    def test_any_anomaly_scope_includes_closed_anomalies_but_not_clean_suppliers(self) -> None:
        rows = self._rows("any_anomaly")
        self.assertEqual({"open", "closed"}, set(rows))
        self.assertEqual(1, rows["closed"]["anomaly_count"])
        self.assertEqual(0, rows["closed"]["open_anomaly_count"])

    def test_all_scope_includes_only_active_suppliers(self) -> None:
        rows = self._rows("all")
        self.assertEqual({"open", "closed", "clean"}, set(rows))

    def test_invalid_scope_is_rejected(self) -> None:
        with patch.object(
            supplier_360_service._connection,
            "get_connection",
            return_value=self.conn,
        ):
            with self.assertRaises(ValueError):
                supplier_360_service.list_supplier_rows(view_scope="unknown")


if __name__ == "__main__":
    unittest.main()
