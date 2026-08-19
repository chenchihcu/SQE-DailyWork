from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from database import connection as _connection
from database import repository
from services.event import _anomaly_action_service, _anomaly_workbench_service
from services.event import _query_service


def _bootstrap_db():
    """Create an isolated SQLite DB with the schema and a supplier + product."""
    tmpdir = tempfile.mkdtemp(prefix="anomaly-overview-parity-")
    db_path = os.path.join(tmpdir, "ncr.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    repository.create_schema(conn)
    supplier = repository.create_supplier_record(conn, supplier_name="OP")
    product = repository.create_product_record(
        conn,
        product_code="OP-001",
        product_name="OP Product",
        supplier_id=supplier,
    )
    anomaly_id = repository.create_anomaly_with_visit_link(
        conn,
        anomaly_date="2026-06-01",
        supplier_id=supplier,
        product_id=product,
        problem_desc="parity problem",
        sync_visit=False,
    )["anomaly_id"]
    visit_id = repository.create_visit(
        conn,
        visit_date="2026-06-01",
        supplier_id=supplier,
        summary="parity visit",
    )
    visit_anomaly = repository.create_anomaly_with_visit_link(
        conn,
        anomaly_date="2026-06-02",
        supplier_id=supplier,
        product_id=product,
        problem_desc="parity linked visit",
        sync_visit=False,
        visit_id=visit_id,
    )["anomaly_id"]
    conn.close()
    return db_path, supplier, product, anomaly_id, visit_anomaly


class OverviewParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path, self.supplier, self.product, self.anomaly_id, self.visit_anomaly = (
            _bootstrap_db()
        )

        def _factory(*args, **kwargs):
            real = sqlite3.connect(
                self.db_path, factory=_connection.ClosingConnection
            )
            real.row_factory = sqlite3.Row
            real.execute("PRAGMA foreign_keys=ON")
            real.execute("PRAGMA journal_mode=WAL")
            real.execute("PRAGMA busy_timeout=5000")
            return real

        self._patcher = mock.patch.object(
            _connection, "get_connection", side_effect=_factory
        )
        self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                pass

    def test_list_events_enriches_anomaly_with_overview(self) -> None:
        _anomaly_action_service.create_action(
            anomaly_id=self.anomaly_id,
            description="下一步",
            due_date="2020-01-01",
        )
        rows = _query_service.list_events({})
        # Both anomalies (one standalone, one with visit_id) must surface overview fields
        anom_rows = [r for r in rows if r.get("event_type") == "ANOMALY"]
        self.assertEqual(len(anom_rows), 2)
        for row in anom_rows:
            self.assertIn("current_action", row)
            self.assertIn("open_action_count", row)
            self.assertIn("overdue", row)
            self.assertIn("root_cause_status", row)
            self.assertIn("corrective_action_status", row)
            self.assertIn("verification_result", row)
            self.assertIn("attachment_count", row)

        standalone = next(r for r in anom_rows if r["event_id"] == self.anomaly_id)
        self.assertTrue(standalone["overdue"])
        self.assertEqual(standalone["open_action_count"], 1)

    def test_list_events_visits_have_no_overview_fields(self) -> None:
        # Create a standalone visit so the list has at least one VISIT row.
        visit_id = None
        with _connection.get_connection() as conn:
            visit_id = repository.create_visit(
                conn,
                visit_date="2026-06-03",
                supplier_id=self.supplier,
                summary="visit only",
            )
        rows = _query_service.list_events({})
        visit_rows = [r for r in rows if r.get("event_type") == "VISIT"]
        self.assertTrue(visit_rows)
        for row in visit_rows:
            self.assertNotIn("overdue", row)
            self.assertNotIn("open_action_count", row)
            self.assertNotIn("current_action", row)

    def test_list_events_by_range_enriches_anomaly_with_overview(self) -> None:
        ca_id = _anomaly_workbench_service.create_corrective_action(
            anomaly_id=self.anomaly_id,
            description="對策",
            effectiveness_verification_required=True,
        )
        _anomaly_workbench_service.complete_corrective_action(
            corrective_action_id=ca_id, implementation_evidence="完成"
        )
        _anomaly_workbench_service.record_verification_with_audit(
            corrective_action_id=ca_id,
            method="監控",
            result="有效",
            verified_by="QA",
        )
        rows = _query_service.list_events_by_range("2026-06-01", "2026-06-30")
        target = next(
            r for r in rows
            if r.get("event_type") == "ANOMALY" and r["event_id"] == self.anomaly_id
        )
        self.assertEqual(target["corrective_action_status"], "有效")
        self.assertEqual(target["verification_result"], "有效")
        self.assertEqual(target["open_action_count"], 0)


if __name__ == "__main__":
    unittest.main()
