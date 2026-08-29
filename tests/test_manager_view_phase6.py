from __future__ import annotations

import os
import sqlite3
import unittest
from contextlib import contextmanager
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QWidget

from database.repo_helpers import CASE_ACTION_TYPE_NEXT_ACTION
from database import manager_view_repository
from database import repository
from ui.widgets.manager_view_page import ManagerViewPage


def _seed_case(conn: sqlite3.Connection, *, suffix: str) -> tuple[str, str]:
    supplier_id = repository.create_supplier_record(
        conn, supplier_name=f"Phase6 Manager Supplier {suffix}"
    )
    product_id = repository.create_product_record(
        conn,
        product_code=f"PH6-MGR-{suffix}",
        product_name="Phase 6 Manager Product",
        supplier_id=supplier_id,
    )
    anomaly_id = repository.create_anomaly_with_visit_link(
        conn,
        anomaly_date="2026-08-20",
        supplier_id=supplier_id,
        product_id=product_id,
        problem_desc=f"manager fixture {suffix}",
        category="外觀",
        sync_visit=False,
        anomaly_no=f"20260820{suffix}",
    )["anomaly_id"]
    return anomaly_id, supplier_id


class ManagerViewRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.anomaly_a, _ = _seed_case(self.conn, suffix="001")
        self.anomaly_b, _ = _seed_case(self.conn, suffix="002")
        repository.create_case_action(
            self.conn,
            anomaly_id=self.anomaly_a,
            action_type=CASE_ACTION_TYPE_NEXT_ACTION,
            description="要求供應商 3 天內回覆",
            owner="SQE 張三",
            due_date="2026-08-19",
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_manager_summary_uses_overview_fields(self) -> None:
        rows = manager_view_repository.list_manager_summary_rows(
            self.conn,
            status="待處理",
        )
        self.assertGreaterEqual(len(rows), 2)
        target = next(row for row in rows if row["anomaly_id"] == self.anomaly_a)
        self.assertIn("root_cause_status", target)
        self.assertIn("corrective_action_status", target)
        self.assertIn("verification_result", target)
        self.assertTrue(target.get("overdue"))

    def test_operational_action_queue_lists_open_actions(self) -> None:
        rows = manager_view_repository.list_operational_action_queue(self.conn)
        self.assertEqual(1, len(rows))
        self.assertEqual(self.anomaly_a, rows[0]["anomaly_id"])
        self.assertEqual("要求供應商 3 天內回覆", rows[0]["description"])

    def test_owner_filter_matches_action_owner_in_summary_and_queue(self) -> None:
        summary_rows = manager_view_repository.list_manager_summary_rows(
            self.conn,
            status="待處理",
            responsible_person="SQE 張三",
        )
        queue_rows = manager_view_repository.list_operational_action_queue(
            self.conn,
            responsible_person="SQE 張三",
        )
        summary_ids = {row["anomaly_id"] for row in summary_rows}
        queue_ids = {row["anomaly_id"] for row in queue_rows}
        self.assertIn(self.anomaly_a, summary_ids)
        self.assertIn(self.anomaly_a, queue_ids)
        self.assertNotIn(self.anomaly_b, summary_ids)
        self.assertNotIn(self.anomaly_b, queue_ids)

    def test_operational_metrics_counts_pending_and_queue(self) -> None:
        metrics = manager_view_repository.get_manager_operational_metrics(self.conn)
        self.assertGreaterEqual(metrics["pending_anomaly_count"], 2)
        self.assertGreaterEqual(metrics["open_queue_action_count"], 1)

    def test_manager_summary_excludes_defect_records(self) -> None:
        """Warehouse defect_records must never appear in manager summary rows."""
        supplier_id = repository.create_supplier_record(
            self.conn, supplier_name="Phase6 Warehouse Supplier"
        )
        self.conn.execute(
            """
            INSERT INTO defect_records(
                defect_no, event_date, processing_line, item_no, qty,
                defect_desc, status, created_at, supplier_id, category
            ) VALUES (
                'NCR-PH6-001', '2026-08-20', '委外加工', 'WH-001', 1,
                'manager fixture warehouse-only', '待處理', '2026-08-20 09:00',
                ?, '外觀'
            )
            """,
            (supplier_id,),
        )
        self.conn.commit()

        summary_rows = manager_view_repository.list_manager_summary_rows(
            self.conn,
            status="待處理",
        )
        queue_rows = manager_view_repository.list_operational_action_queue(self.conn)
        metrics = manager_view_repository.get_manager_operational_metrics(self.conn)

        anomaly_ids = {row["anomaly_id"] for row in summary_rows}
        self.assertIn(self.anomaly_a, anomaly_ids)
        self.assertIn(self.anomaly_b, anomaly_ids)
        self.assertEqual(2, len({row["anomaly_id"] for row in summary_rows}))
        self.assertEqual(2, metrics["pending_anomaly_count"])
        self.assertTrue(
            all(
                str(row.get("event_type") or row.get("anomaly_status") or "")
                not in {"defect_records", "NCR"}
                for row in summary_rows
            )
        )
        self.assertTrue(
            all("warehouse-only" not in str(row.get("problem_desc") or "") for row in queue_rows)
        )


class ManagerViewPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls._host = QWidget()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._host.close()
        cls._host.deleteLater()
        app = QApplication.instance()
        if app is not None:
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()

    def setUp(self) -> None:
        self._pages: list[ManagerViewPage] = []
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.anomaly_id, _ = _seed_case(self.conn, suffix="101")
        self.conn.commit()

        @contextmanager
        def _fake_connection():
            yield self.conn

        self._conn_patcher = mock.patch(
            "services.manager_view_service._connection.get_connection",
            side_effect=_fake_connection,
        )
        self._conn_patcher.start()

    def tearDown(self) -> None:
        self._conn_patcher.stop()
        self.conn.close()
        for page in self._pages:
            page.close()
            page.deleteLater()
        self._pages.clear()
        app = QApplication.instance()
        if app is not None:
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()

    def _make_page(self, parent: QWidget | None = None) -> ManagerViewPage:
        page = ManagerViewPage(parent if parent is not None else self._host)
        self._pages.append(page)
        return page

    def test_page_renders_summary_and_queue_tabs(self) -> None:
        page = self._make_page()
        page.refresh_data()
        self.assertEqual(2, page._tabs.count())
        self.assertGreaterEqual(page._summary_table.rowCount(), 1)
        self.assertGreaterEqual(page._queue_table.rowCount(), 0)

    def test_open_summary_row_routes_to_workbench(self) -> None:
        main_window = mock.Mock()
        page = self._make_page(main_window)
        page.refresh_data()
        page._open_anomaly(self.anomaly_id)
        main_window.open_anomaly_management.assert_called_once_with(self.anomaly_id)
