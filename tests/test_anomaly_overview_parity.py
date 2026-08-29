from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from database import connection as _connection
from database import repository
from services.event import _case_action_service
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
        _case_action_service.create_case_action(
            anomaly_id=self.anomaly_id,
            action_type="NEXT_ACTION",
            description="下一步",
            due_date="2020-01-01",
            execution_status="執行中",
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
        with _connection.get_connection() as conn:
            repository.create_visit(
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
        action_id = _case_action_service.create_case_action(
            anomaly_id=self.anomaly_id,
            action_type="CORRECTIVE_ACTION",
            description="對策",
            execution_status="執行中",
            verification_required=True,
        )
        _case_action_service.complete_case_action(
            action_id,
            implementation_evidence="完成",
        )
        _case_action_service.record_action_verification(
            action_id=action_id,
            method="監控",
            result="有效",
            verified_by="QA",
        )
        rows = _query_service.list_events_by_range("2026-06-01", "2026-06-30")
        target = next(
            r for r in rows
            if r.get("event_type") == "ANOMALY" and r["event_id"] == self.anomaly_id
        )
        self.assertEqual(target["corrective_action_status"], "已完成")
        self.assertEqual(target["verification_result"], "有效")
        self.assertEqual(target["open_action_count"], 0)

    def test_overview_card_includes_repeat_link_count(self) -> None:
        with _connection.get_connection() as conn:
            card = repository.get_anomaly_overview_card(conn, self.anomaly_id)
        self.assertIn("repeat_link_count", card)
        self.assertEqual(0, card["repeat_link_count"])

    def test_list_events_repeat_link_count_matches_overview_ssot(self) -> None:
        rows = _query_service.list_events({})
        target = next(r for r in rows if r["event_id"] == self.anomaly_id)
        with _connection.get_connection() as conn:
            card = repository.get_anomaly_overview_card(conn, self.anomaly_id)
        self.assertEqual(card["repeat_link_count"], target["repeat_link_count"])

    def test_list_events_by_range_includes_trace_fields(self) -> None:
        with _connection.get_connection() as conn:
            conn.execute(
                """
                UPDATE anomalies
                SET anomaly_source = ?, material_receipt_no = ?
                WHERE id = ?
                """,
                ("進料檢驗 (IQC)", "MR-9001", self.anomaly_id),
            )
            conn.commit()
        rows = _query_service.list_events_by_range("2026-06-01", "2026-06-30")
        target = next(
            r for r in rows
            if r.get("event_type") == "ANOMALY" and r["event_id"] == self.anomaly_id
        )
        self.assertEqual("進料檢驗 (IQC)", target.get("anomaly_source"))
        self.assertEqual("MR-9001", target.get("material_receipt_no"))


if __name__ == "__main__":
    unittest.main()
