from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QFrame

from services.event import _anomaly_service, _anomaly_workbench_service
from services.event import _anomaly_action_service
from ui.widgets.anomaly_overview_dialog import AnomalyOverviewDialog


class AnomalyOverviewDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _dialog_patchers(self):
        detail = {
            "anomaly_no": "20260601001",
            "supplier_name": "Ov",
            "status": "待處理",
            "pending_items": "",
            "responsible_person": "",
            "due_date": "",
        }
        overview = {
            "status": "待處理",
            "overdue": False,
            "current_action": None,
            "open_action_count": 0,
            "root_cause_status": "尚未開始",
            "corrective_action_status": "—",
            "verification_result": "—",
            "has_analysis_notes": False,
        }
        patches = [
            mock.patch.object(
                _anomaly_service, "get_anomaly_detail", return_value=detail
            ),
            mock.patch.object(
                _anomaly_workbench_service, "get_overview_card", return_value=overview
            ),
            mock.patch.object(
                _anomaly_workbench_service, "get_root_cause", return_value=None
            ),
            mock.patch.object(
                _anomaly_workbench_service, "list_analysis_notes", return_value=[]
            ),
            mock.patch.object(
                _anomaly_workbench_service, "list_corrective_actions", return_value=[]
            ),
            mock.patch.object(
                _anomaly_workbench_service, "list_eight_d_reviews", return_value=[]
            ),
            mock.patch.object(
                _anomaly_workbench_service, "list_attachments", return_value=[]
            ),
            mock.patch.object(
                _anomaly_workbench_service, "list_timeline", return_value=[]
            ),
            mock.patch.object(
                _anomaly_action_service, "list_actions", return_value=[]
            ),
        ]
        return patches

    def test_builds_read_only_overview(self) -> None:
        self.patchers = self._dialog_patchers()
        for p in self.patchers:
            p.start()
        try:
            dialog = AnomalyOverviewDialog("dummy-id", parent=None)
            self.assertIsInstance(dialog, QDialog)
            self.assertIsNotNone(dialog.findChild(QFrame, "AnomalyOverviewHeader"))
            self.assertIsNotNone(
                dialog.findChild(QFrame, "AnomalyOverviewBodyScroll")
            )
            self.assertIsNotNone(dialog.findChild(QFrame, "AnomalyOverviewFooter"))
        finally:
            for p in self.patchers:
                p.stop()


if __name__ == "__main__":
    unittest.main()
