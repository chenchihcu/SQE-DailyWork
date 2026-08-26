from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from services.event import _case_action_service
from ui.widgets.anomaly_action_dialog import AddAnomalyActionDialog


class AddAnomalyActionDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self) -> AddAnomalyActionDialog:
        return AddAnomalyActionDialog("anomaly-1", parent=None)

    def test_requires_description_to_enable_save(self) -> None:
        dialog = self._dialog()
        self.assertFalse(dialog._save_button.isEnabled())
        dialog.description_input.setPlainText("要求 FA 報告")
        self.assertTrue(dialog._save_button.isEnabled())

    def test_submit_calls_service_and_emits(self) -> None:
        dialog = self._dialog()
        dialog.description_input.setPlainText("要求 8D")
        dialog.owner_input.setText("Alice")
        emitted = []
        dialog.action_created.connect(lambda aid: emitted.append(aid))
        with mock.patch.object(
            _case_action_service, "create_case_action", return_value="act-1"
        ) as mk:
            dialog._on_submit()
        mk.assert_called_once_with(
            anomaly_id="anomaly-1",
            action_type="NEXT_ACTION",
            description="要求 8D",
            owner="Alice",
            due_date=dialog.due_date_edit.date().toString("yyyy-MM-dd"),
            execution_status="已規劃",
            verification_required=False,
        )
        self.assertEqual(emitted, ["act-1"])

    def test_empty_description_does_not_call_service(self) -> None:
        dialog = self._dialog()
        with mock.patch.object(
            _case_action_service, "create_case_action"
        ) as mk:
            dialog._on_submit()
        mk.assert_not_called()


if __name__ == "__main__":
    unittest.main()
