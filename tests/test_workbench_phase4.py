from __future__ import annotations

import os
import sqlite3
import unittest
from contextlib import contextmanager
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from database import repository
from database.repo_helpers import (
    ANOMALY_AUDIT_CASE_CLOSED,
    ANOMALY_AUDIT_CASE_REOPENED,
)
from services.event import _anomaly_service
from ui.widgets.close_anomaly_dialog import CloseAnomalyDialog
from ui.widgets.reopen_anomaly_dialog import ReopenAnomalyDialog


def _seed_anomaly(conn: sqlite3.Connection) -> str:
    supplier_id = repository.create_supplier_record(
        conn, supplier_name="Phase4 Workbench Supplier"
    )
    product_id = repository.create_product_record(
        conn,
        product_code="PH4-WB-001",
        product_name="Phase 4 Workbench Product",
        supplier_id=supplier_id,
    )
    return repository.create_anomaly_with_visit_link(
        conn,
        anomaly_date="2026-08-26",
        supplier_id=supplier_id,
        product_id=product_id,
        problem_desc="phase 4 workbench fixture",
        sync_visit=False,
    )["anomaly_id"]


class WorkbenchPhase4ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        repository.create_schema(self.conn)
        self.anomaly_id = _seed_anomaly(self.conn)

        @contextmanager
        def _fake_connection():
            yield self.conn

        self._conn_patcher = mock.patch(
            "services.event._anomaly_service._connection.get_connection",
            side_effect=_fake_connection,
        )
        self._conn_patcher.start()
        self._snapshot_patcher = mock.patch(
            "services.event._anomaly_service._write_snapshot_with_warning",
            return_value=[],
        )
        self._snapshot_patcher.start()

    def tearDown(self) -> None:
        self._snapshot_patcher.stop()
        self._conn_patcher.stop()
        self.conn.close()

    def test_close_anomaly_writes_case_closed_audit(self) -> None:
        _anomaly_service.close_anomaly(
            self.anomaly_id,
            "供應商已更換治具並完成首件確認。",
            closed_by="SQE 王小明",
            closed_at="2026-08-26",
        )
        detail = repository.get_anomaly_detail(self.conn, self.anomaly_id)
        assert detail is not None
        self.assertEqual("已結案", detail["status"])
        logs = repository.list_anomaly_audit_logs(self.conn, self.anomaly_id)
        closed_logs = [row for row in logs if row["action"] == ANOMALY_AUDIT_CASE_CLOSED]
        self.assertEqual(1, len(closed_logs))
        self.assertIn("供應商已更換治具", closed_logs[0]["after_value"])

    def test_reopen_anomaly_requires_reason_and_writes_audit(self) -> None:
        repository.close_anomaly(
            self.conn,
            anomaly_id=self.anomaly_id,
            improvement_desc="initial closure",
            closed_at="2026-08-26",
        )
        with self.assertRaises(ValueError):
            _anomaly_service.reopen_anomaly(self.anomaly_id, reopen_reason="   ")

        _anomaly_service.reopen_anomaly(
            self.anomaly_id,
            reopen_reason="供應商回報同缺陷再發，需重新調查。",
            actor_name="SQE 李四",
        )
        detail = repository.get_anomaly_detail(self.conn, self.anomaly_id)
        assert detail is not None
        self.assertEqual("待處理", detail["status"])
        self.assertEqual("", detail["improvement_desc"])
        self.assertIsNone(detail["closed_at"])
        logs = repository.list_anomaly_audit_logs(self.conn, self.anomaly_id)
        reopened = [row for row in logs if row["action"] == ANOMALY_AUDIT_CASE_REOPENED]
        self.assertEqual(1, len(reopened))
        self.assertIn("closed_at=", reopened[0]["before_value"])
        self.assertIn("供應商回報", reopened[0]["after_value"])

    def test_reopen_refreshes_monthly_cache_when_commit_deferred(self) -> None:
        repository.close_anomaly(
            self.conn,
            anomaly_id=self.anomaly_id,
            improvement_desc="cache refresh closure",
            closed_at="2026-08-26",
        )
        with mock.patch.object(
            repository, "refresh_monthly_cache"
        ) as refresh_mock:
            repository.reopen_anomaly(self.conn, self.anomaly_id, _commit=False)
            self.conn.commit()
        self.assertTrue(refresh_mock.called)

    def test_timeline_includes_close_and_reopen_audit_events(self) -> None:
        _anomaly_service.close_anomaly(
            self.anomaly_id,
            "closure for timeline",
            closed_at="2026-08-26",
        )
        _anomaly_service.reopen_anomaly(
            self.anomaly_id,
            reopen_reason="reopen for timeline",
        )
        timeline = repository.list_anomaly_timeline(self.conn, self.anomaly_id)
        kinds = {row.get("kind") for row in timeline}
        self.assertIn(ANOMALY_AUDIT_CASE_CLOSED, kinds)
        self.assertIn(ANOMALY_AUDIT_CASE_REOPENED, kinds)


class WorkbenchPhase4DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    @mock.patch("ui.widgets.close_anomaly_dialog.event_service.get_anomaly_detail")
    def test_close_dialog_uses_evidence_panel(self, mock_detail) -> None:
        mock_detail.return_value = {
            "anomaly_date": "2026-08-26",
            "closed_at": "",
            "closed_by": "",
            "improvement_desc": "",
        }
        dialog = CloseAnomalyDialog("anomaly-1", "測試問題", parent=None)
        self.assertTrue(hasattr(dialog, "evidence_panel"))
        self.assertFalse(hasattr(dialog, "attachment_editor"))

    @mock.patch("ui.widgets.reopen_anomaly_dialog.event_service.reopen_anomaly")
    def test_reopen_dialog_requires_reason_before_submit(self, mock_reopen) -> None:
        dialog = ReopenAnomalyDialog("anomaly-1", "20260826001", parent=None)
        self.assertFalse(dialog._save_button.isEnabled())
        dialog.reason_input.setPlainText("需要補充調查")
        dialog._update_validation()
        self.assertTrue(dialog._save_button.isEnabled())


if __name__ == "__main__":
    unittest.main()
