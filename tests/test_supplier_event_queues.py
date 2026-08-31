from __future__ import annotations

import os
import sqlite3
import unittest
from contextlib import contextmanager
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QWidget

from database import manager_view_repository
from database import repository
from database.repo_helpers import CASE_ACTION_TYPE_NEXT_ACTION
from ui.sidebar_nav import PAGE_EVENT_OVERDUE
from ui.widgets.supplier_event_queue_page import SupplierEventQueuePage


def _seed_case(conn: sqlite3.Connection, *, suffix: str) -> str:
    supplier_id = repository.create_supplier_record(
        conn, supplier_name=f"Queue Supplier {suffix}"
    )
    product_id = repository.create_product_record(
        conn,
        product_code=f"QUEUE-{suffix}",
        product_name="Queue Product",
        supplier_id=supplier_id,
    )
    anomaly_id = repository.create_anomaly_with_visit_link(
        conn,
        anomaly_date="2026-08-20",
        supplier_id=supplier_id,
        product_id=product_id,
        problem_desc=f"queue fixture {suffix}",
        category="外觀",
        sync_visit=False,
        anomaly_no=f"20260820{suffix}",
    )["anomaly_id"]
    return anomaly_id


class SupplierEventQueueRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.anomaly_a = _seed_case(self.conn, suffix="001")
        self.anomaly_b = _seed_case(self.conn, suffix="002")
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

    def test_queue_counts_align_with_lists(self) -> None:
        counts = manager_view_repository.get_supplier_event_queue_counts(self.conn)
        overdue_rows = manager_view_repository.list_overdue_case_queue_rows(self.conn)
        rca_rows = manager_view_repository.list_root_cause_pending_case_queue_rows(self.conn)
        action_rows = manager_view_repository.list_operational_action_queue(self.conn)
        self.assertEqual(counts["overdue_anomaly_count"], len(overdue_rows))
        self.assertEqual(counts["root_cause_pending_count"], len(rca_rows))
        self.assertEqual(counts["open_queue_action_count"], len(action_rows))
        self.assertIn(self.anomaly_a, {row["anomaly_id"] for row in overdue_rows})
        self.assertEqual(1, len(action_rows))


class SupplierEventQueuePageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls._host = QWidget()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._host.close()
        cls._host.deleteLater()

    def setUp(self) -> None:
        self._pages: list[SupplierEventQueuePage] = []
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.anomaly_id = _seed_case(self.conn, suffix="101")
        repository.create_case_action(
            self.conn,
            anomaly_id=self.anomaly_id,
            action_type=CASE_ACTION_TYPE_NEXT_ACTION,
            description="queue page action",
            owner="SQE 李四",
            due_date="2026-08-19",
        )
        self.conn.commit()

        @contextmanager
        def _fake_connection():
            yield self.conn

        self._conn_patcher = mock.patch(
            "services.supplier_event_queue_service._connection.get_connection",
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

    def test_overdue_queue_row_opens_workbench_with_source_key(self) -> None:
        main_window = mock.Mock()
        page = SupplierEventQueuePage(
            main_window,
            queue="overdue",
            page_key=PAGE_EVENT_OVERDUE,
        )
        self._pages.append(page)
        page.refresh_data()
        self.assertGreaterEqual(page._table.rowCount(), 1)
        page._on_row_clicked(0, 0)
        main_window.open_anomaly_management.assert_called_once_with(
            self.anomaly_id,
            source_page_key=PAGE_EVENT_OVERDUE,
        )


if __name__ == "__main__":
    unittest.main()
