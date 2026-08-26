from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from unittest import mock

from database import connection as _connection
from database import repository
from services import event_service
from services.event import _case_action_service, _anomaly_workbench_service


def _bootstrap_db():
    """Create an isolated SQLite DB with the schema and one supplier/product."""
    tmpdir = tempfile.mkdtemp(prefix="anomaly-actions-svc-")
    db_path = os.path.join(tmpdir, "ncr.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    repository.create_schema(conn)
    supplier = repository.create_supplier_record(conn, supplier_name="Svc")
    product = repository.create_product_record(
        conn,
        product_code="SVC-001",
        product_name="Svc Product",
        supplier_id=supplier,
    )
    anomaly_id = repository.create_anomaly_with_visit_link(
        conn,
        anomaly_date="2026-06-01",
        supplier_id=supplier,
        product_id=product,
        problem_desc="svc test",
        sync_visit=False,
    )["anomaly_id"]
    conn.close()
    return db_path, supplier, product, anomaly_id


class AnomalyActionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path, self.supplier, self.product, self.anomaly_id = _bootstrap_db()

        def _factory(*args, **kwargs):
            real = sqlite3.connect(
                self.db_path, factory=_connection.ClosingConnection
            )
            real.row_factory = sqlite3.Row
            real.execute("PRAGMA foreign_keys=ON")
            real.execute("PRAGMA journal_mode=WAL")
            real.execute("PRAGMA busy_timeout=5000")
            return real

        # Every service module does ``from database import connection as
        # _connection`` and calls ``_connection.get_connection()``, so patching
        # that single function on the module is enough to redirect all services
        # to our disposable database.
        self._p_get_connection = mock.patch.object(
            _connection, "get_connection", side_effect=_factory
        )
        self._p_get_connection.start()

    def tearDown(self) -> None:
        self._p_get_connection.stop()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                # Windows may hold a lock on the WAL until flush; ignore.
                pass

    # --- CRUD wrappers -------------------------------------------------

    def test_create_list_and_complete(self) -> None:
        action_id = _case_action_service.create_case_action(
            anomaly_id=self.anomaly_id,
            action_type="NEXT_ACTION",
            description="Send 8D",
            owner="Alice",
            due_date="2026-07-15",
            execution_status="執行中",
        )
        actions = _case_action_service.list_case_actions(self.anomaly_id)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["description"], "Send 8D")
        self.assertEqual(actions[0]["execution_status"], "執行中")

        _case_action_service.complete_case_action(
            action_id, completion_note="8D submitted"
        )
        actions = _case_action_service.list_case_actions(self.anomaly_id)
        self.assertEqual(actions[0]["execution_status"], "已完成")
        self.assertEqual(actions[0]["completion_note"], "8D submitted")

    def test_update_only_open_actions(self) -> None:
        action_id = _case_action_service.create_case_action(
            anomaly_id=self.anomaly_id,
            action_type="NEXT_ACTION",
            description="original",
            execution_status="執行中",
        )
        _case_action_service.complete_case_action(action_id)
        with self.assertRaisesRegex(ValueError, "planned or in-progress"):
            _case_action_service.update_case_action(action_id, description="new")

    def test_cancel_marks_action(self) -> None:
        action_id = _case_action_service.create_case_action(
            anomaly_id=self.anomaly_id,
            action_type="NEXT_ACTION",
            description="reschedule",
            due_date="2026-08-01",
            execution_status="執行中",
        )
        _case_action_service.cancel_case_action(action_id, cancel_note="x")
        actions = _case_action_service.list_case_actions(self.anomaly_id)
        self.assertEqual(actions[0]["execution_status"], "已取消")

    def test_is_overdue_uses_action_due_date(self) -> None:
        _case_action_service.create_case_action(
            anomaly_id=self.anomaly_id,
            action_type="NEXT_ACTION",
            description="late",
            due_date="2020-01-01",
        )
        self.assertTrue(_case_action_service.is_anomaly_overdue(self.anomaly_id))

    def test_build_lifecycle_card_returns_safe_defaults_for_missing(self) -> None:
        self.assertEqual(_case_action_service.list_case_actions("nope"), [])
        self.assertIsNone(_case_action_service.get_current_case_action("nope"))

    def test_build_lifecycle_card_aggregates_counts(self) -> None:
        a1 = _case_action_service.create_case_action(
            anomaly_id=self.anomaly_id,
            action_type="NEXT_ACTION",
            description="done",
            due_date="2026-06-01",
            execution_status="執行中",
        )
        _case_action_service.complete_case_action(a1)
        a2 = _case_action_service.create_case_action(
            anomaly_id=self.anomaly_id,
            action_type="NEXT_ACTION",
            description="cancelled",
            due_date="2026-06-01",
        )
        _case_action_service.cancel_case_action(a2, cancel_note="duplicate")
        active = _case_action_service.create_case_action(
            anomaly_id=self.anomaly_id,
            action_type="NEXT_ACTION",
            description="now",
            due_date="2026-07-01",
        )
        actions = _case_action_service.list_case_actions(self.anomaly_id)
        card = _anomaly_workbench_service.get_overview_card(self.anomaly_id)
        self.assertEqual(
            sum(1 for row in actions if row["execution_status"] == "已完成"),
            1,
        )
        self.assertEqual(
            sum(1 for row in actions if row["execution_status"] == "已取消"),
            1,
        )
        self.assertIsNotNone(card["current_action"])
        self.assertEqual(card["current_action"]["id"], active)

    def test_event_service_export_still_works(self) -> None:
        # Smoke check: existing event_service interface is untouched.
        details = event_service.get_anomaly_detail(self.anomaly_id)
        self.assertEqual(details["status"], "待處理")
        listing = event_service.list_events({})
        self.assertTrue(
            any(
                row.get("id") == self.anomaly_id
                or row.get("event_id") == self.anomaly_id
                for row in listing
            )
        )


if __name__ == "__main__":
    unittest.main()
