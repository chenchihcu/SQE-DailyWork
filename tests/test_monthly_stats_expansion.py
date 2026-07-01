from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

import pandas as pd

from database import repository
from services import event_service


class MonthlyStatsExpansionRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = base_tmp_dir / f"sqe_monthly_stats_{uuid4().hex}.db"
        self.export_path = base_tmp_dir / f"monthly_all_export_{uuid4().hex}.xlsx"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()
        if self.export_path.exists():
            self.export_path.unlink()

    def _create_supplier(self, name: str) -> str:
        return repository.create_supplier_record(self.conn, supplier_name=name)

    def _create_anomaly(self, supplier_id: str, anomaly_date: str) -> str:
        return repository.create_anomaly(
            self.conn,
            anomaly_date=anomaly_date,
            supplier_id=supplier_id,
            problem_desc=f"Problem at {anomaly_date}",
        )

    def _create_visit(self, supplier_id: str, visit_date: str) -> str:
        return repository.create_visit(
            self.conn,
            visit_date=visit_date,
            supplier_id=supplier_id,
            summary=f"Visit at {visit_date}",
        )

    def _set_due_date(self, anomaly_no: str, due_date: str) -> None:
        self.conn.execute(
            "UPDATE anomalies SET due_date = ? WHERE anomaly_no = ?",
            (due_date, anomaly_no),
        )
        self.conn.commit()

    def _force_close(self, anomaly_no: str, closed_at: str) -> None:
        self.conn.execute(
            """
            UPDATE anomalies
            SET status = '已結案',
                improvement_desc = 'closed in test',
                closed_at = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE anomaly_no = ?
            """,
            (closed_at, anomaly_no),
        )
        self.conn.commit()

    def test_get_monthly_stats_empty_month_returns_zeroes_and_no_ranking(self) -> None:
        summary = repository.get_monthly_stats(self.conn, "202604")

        self.assertEqual("202604", summary["yyyymm"])
        self.assertEqual(0, summary["visit_count"])
        self.assertEqual(0, summary["closed_anomaly_count"])
        self.assertEqual(0, summary["anomaly_count"])
        self.assertEqual(0, summary["open_anomaly_count"])
        self.assertEqual(0.0, summary["close_rate_pct"])
        self.assertEqual(0.0, summary["anomaly_visit_ratio"])
        self.assertEqual(0, summary["supplier_coverage_count"])
        self.assertEqual([], summary["top_suppliers_by_anomaly"])

    def test_get_monthly_stats_counts_only_selected_month_and_computes_ratios(self) -> None:
        supplier_id = self._create_supplier("Supplier-A")

        self._create_anomaly(supplier_id, "2026-04-02")
        close_in_april = self._create_anomaly(supplier_id, "2026-04-03")
        self._force_close(close_in_april, "2026-04-10")

        created_in_march = self._create_anomaly(supplier_id, "2026-03-20")
        self._force_close(created_in_march, "2026-04-11")

        self._create_visit(supplier_id, "2026-04-05")
        self._create_visit(supplier_id, "2026-04-12")
        self._create_visit(supplier_id, "2026-03-08")

        summary = repository.get_monthly_stats(self.conn, "202604")

        self.assertEqual(2, summary["anomaly_count"])
        self.assertEqual(2, summary["visit_count"])
        self.assertEqual(2, summary["closed_anomaly_count"])
        self.assertEqual(1, summary["open_anomaly_count"])
        self.assertEqual(100.0, summary["close_rate_pct"])
        self.assertEqual(1.0, summary["anomaly_visit_ratio"])
        self.assertEqual(1, summary["supplier_coverage_count"])
        self.assertEqual(1, len(summary["top_suppliers_by_anomaly"]))
        self.assertEqual("Supplier-A", summary["top_suppliers_by_anomaly"][0]["supplier_name"])

    def test_get_monthly_stats_ranking_obeys_priority_without_top5_limit(self) -> None:
        suppliers = {
            "Alpha": self._create_supplier("Alpha"),
            "Beta": self._create_supplier("Beta"),
            "Delta": self._create_supplier("Delta"),
            "Gamma": self._create_supplier("Gamma"),
            "Epsilon": self._create_supplier("Epsilon"),
            "Zeta": self._create_supplier("Zeta"),
        }
        test_data = {
            "Alpha": {"anomalies": 2, "visits": 1},
            "Beta": {"anomalies": 2, "visits": 3},
            "Delta": {"anomalies": 1, "visits": 5},
            "Gamma": {"anomalies": 1, "visits": 5},
            "Epsilon": {"anomalies": 1, "visits": 0},
            "Zeta": {"anomalies": 1, "visits": 0},
        }

        for supplier_name, data in test_data.items():
            supplier_id = suppliers[supplier_name]
            for _ in range(data["anomalies"]):
                self._create_anomaly(supplier_id, "2026-04-03")
            for _ in range(data["visits"]):
                self._create_visit(supplier_id, "2026-04-07")

        summary = repository.get_monthly_stats(self.conn, "202604")
        top_names = [item["supplier_name"] for item in summary["top_suppliers_by_anomaly"]]

        self.assertEqual(6, len(top_names))
        self.assertEqual(
            ["Beta", "Alpha", "Delta", "Gamma", "Epsilon", "Zeta"],
            top_names,
        )

    def test_list_events_overdue_only_matches_monthly_overdue_count(self) -> None:
        supplier_id = self._create_supplier("Supplier-A")

        overdue_no = self._create_anomaly(supplier_id, "2026-04-02")
        self._set_due_date(overdue_no, "2020-01-01")  # 已逾期（待處理且過期）
        future_no = self._create_anomaly(supplier_id, "2026-04-03")
        self._set_due_date(future_no, "2999-12-31")  # 尚未到期
        self._create_anomaly(supplier_id, "2026-04-04")  # due_date 空白 → 不算逾期

        rows = repository.list_events(
            self.conn,
            event_type="ANOMALY",
            status="待處理",
            yyyymm="202604",
            overdue_only=True,
        )

        self.assertEqual(1, len(rows))
        self.assertEqual(overdue_no, rows[0]["ref_no"])

        summary = repository.get_monthly_stats(self.conn, "202604")
        self.assertEqual(summary["overdue_open_anomaly_count"], len(rows))

    def test_list_events_overdue_only_excludes_visits(self) -> None:
        supplier_id = self._create_supplier("Supplier-A")
        self._create_visit(supplier_id, "2026-04-05")
        overdue_no = self._create_anomaly(supplier_id, "2026-04-02")
        self._set_due_date(overdue_no, "2020-01-01")

        rows = repository.list_events(
            self.conn,
            event_type="ALL",
            status="待處理",
            overdue_only=True,
        )

        self.assertEqual(1, len(rows))
        self.assertTrue(all(row["event_type"] == "ANOMALY" for row in rows))

    def test_export_monthly_excel_accepts_all_period_from_stats_page(self) -> None:
        supplier_id = self._create_supplier("Supplier-A")
        self._create_anomaly(supplier_id, "2026-04-02")
        self._create_visit(supplier_id, "2026-05-06")

        with patch.object(event_service, "get_connection", return_value=self.conn):
            ok, msg = event_service.export_monthly_excel(str(self.export_path), "ALL")

        self.assertTrue(ok, msg)
        self.assertTrue(self.export_path.exists())

        with pd.ExcelFile(self.export_path) as workbook:
            summary_df = pd.read_excel(workbook, sheet_name="月統計")
            detail_df = pd.read_excel(workbook, sheet_name="明細")

        self.assertEqual("全期項目", summary_df.loc[0, "月份"])
        self.assertEqual(2, len(detail_df))
        self.assertEqual({"異常", "訪廠"}, set(detail_df["類型"]))


class MonthlyStatsExpansionExportTests(unittest.TestCase):
    def setUp(self) -> None:
        base_tmp_dir = Path("scratch")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.export_path = base_tmp_dir / f"monthly_export_{uuid4().hex}.xlsx"

    def tearDown(self) -> None:
        if self.export_path.exists():
            self.export_path.unlink()

    def test_export_monthly_excel_contains_expanded_summary_and_supplier_ranking(self) -> None:
        mocked_stats = {
            "yyyymm": "202604",
            "visit_count": 6,
            "closed_anomaly_count": 3,
            "anomaly_count": 4,
            "open_anomaly_count": 1,
            "close_rate_pct": 75.0,
            "anomaly_visit_ratio": 0.67,
            "supplier_coverage_count": 2,
            "top_suppliers_by_anomaly": [
                {
                    "supplier_name": "Supplier-B",
                    "anomaly_count": 3,
                    "visit_count": 4,
                    "closed_anomaly_count": 2,
                    "open_anomaly_count": 1,
                    "close_rate_pct": 66.7,
                },
                {
                    "supplier_name": "Supplier-A",
                    "anomaly_count": 1,
                    "visit_count": 2,
                    "closed_anomaly_count": 1,
                    "open_anomaly_count": 0,
                    "close_rate_pct": 100.0,
                },
            ],
        }
        mocked_rows = [
            {
                "event_date": "2026-04-08",
                "event_type": "ANOMALY",
                "supplier_name": "Supplier-B",
                "content": "Issue 1",
                "status": "待處理",
            },
            {
                "event_date": "2026-04-10",
                "event_type": "VISIT",
                "supplier_name": "Supplier-A",
                "content": "Visit note",
                "status": "已完成",
            },
        ]

        with (
            patch("services.event_service.get_monthly_stats", return_value=mocked_stats),
            patch("services.event_service.list_events", return_value=mocked_rows),
        ):
            ok, msg = event_service.export_monthly_excel(str(self.export_path), "202604")

        self.assertTrue(ok, msg)
        self.assertTrue(self.export_path.exists())

        with pd.ExcelFile(self.export_path) as workbook:
            sheets = workbook.sheet_names
            summary_df = pd.read_excel(workbook, sheet_name="月統計")
            ranking_df = pd.read_excel(workbook, sheet_name="供應商排行")
            detail_df = pd.read_excel(workbook, sheet_name="明細")
        self.assertIn("月統計", sheets)
        self.assertIn("供應商排行", sheets)
        self.assertIn("明細", sheets)

        self.assertEqual(
            [
                "月份",
                "本月異常數",
                "訪廠數",
                "結案數",
                "未結案數",
                "結案率(%)",
                "異常/訪廠比",
                "供應商覆蓋數",
            ],
            list(summary_df.columns),
        )
        self.assertEqual(
            ["排名", "供應商", "異常數", "訪廠數", "結案數", "未結案數", "結案率(%)"],
            list(ranking_df.columns),
        )
        self.assertEqual(2, len(ranking_df))
        self.assertEqual(2, len(detail_df))


if __name__ == "__main__":
    unittest.main()
