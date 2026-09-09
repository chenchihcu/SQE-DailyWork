from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from services.event import _case_action_service
from ui.widgets.edit_anomaly_action_dialog import EditAnomalyActionDialog


class EditAnomalyActionDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _action(self, **overrides) -> dict:
        payload = {
            "id": "act-parent",
            "anomaly_id": "anomaly-1",
            "action_type": "CONTAINMENT",
            "description": "單一處置",
            "owner": "Alice",
            "due_date": "2026-09-16",
            "execution_status": "已規劃",
            "verification_required": False,
        }
        payload.update(overrides)
        return payload

    def test_single_row_updates_existing_action(self) -> None:
        dialog = EditAnomalyActionDialog(self._action(), parent=None)
        dialog.action_items_input.set_items(
            [
                {
                    "description": "更新後處置",
                    "owner": "Bob",
                    "due_date": "2026-09-20",
                }
            ]
        )
        emitted = []
        dialog.action_updated.connect(lambda aid: emitted.append(aid))
        with mock.patch.object(
            _case_action_service, "update_case_action"
        ) as update_mk, mock.patch.object(
            _case_action_service, "split_case_action"
        ) as split_mk:
            dialog._on_submit()
        update_mk.assert_called_once_with(
            "act-parent",
            action_type="CONTAINMENT",
            description="更新後處置",
            owner="Bob",
            due_date="2026-09-20",
            verification_required=False,
        )
        split_mk.assert_not_called()
        self.assertEqual(emitted, ["act-parent"])

    def test_multiple_rows_split_action(self) -> None:
        dialog = EditAnomalyActionDialog(
            self._action(
                description="1. 第一項\n2. 第二項",
            ),
            parent=None,
        )
        items = dialog.action_items_input.get_items()
        self.assertEqual(len(items), 2)
        emitted = []
        dialog.action_updated.connect(lambda aid: emitted.append(aid))
        with mock.patch.object(
            _case_action_service,
            "split_case_action",
            return_value=["act-new-1", "act-new-2"],
        ) as split_mk, mock.patch.object(
            _case_action_service, "update_case_action"
        ) as update_mk:
            dialog._on_submit()
        split_mk.assert_called_once()
        update_mk.assert_not_called()
        self.assertEqual(emitted, ["act-new-1"])


if __name__ == "__main__":
    unittest.main()
