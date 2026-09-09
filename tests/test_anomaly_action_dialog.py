from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from database.repo_helpers import (
    CASE_ACTION_TYPE_CONTAINMENT,
    CASE_ACTION_TYPE_NEXT_ACTION,
    ordered_case_action_type_labels,
)
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
        dialog.action_items_input.set_items(
            [{"description": "要求 FA 報告", "owner": "", "due_date": ""}]
        )
        self.assertTrue(dialog._save_button.isEnabled())

    def test_action_type_combo_uses_8d_order_without_next_action(self) -> None:
        dialog = self._dialog()
        labels = [dialog.action_type_combo.itemText(i) for i in range(dialog.action_type_combo.count())]
        expected = [label for _value, label in ordered_case_action_type_labels(for_ui=True)]
        self.assertEqual(expected, labels)
        self.assertNotIn(CASE_ACTION_TYPE_NEXT_ACTION, [
            dialog.action_type_combo.itemData(i)
            for i in range(dialog.action_type_combo.count())
        ])
        self.assertEqual(
            CASE_ACTION_TYPE_CONTAINMENT,
            dialog.action_type_combo.currentData(),
        )

    def test_submit_calls_batch_service_and_emits(self) -> None:
        dialog = self._dialog()
        dialog.action_items_input.set_items(
            [
                {
                    "description": "要求 8D",
                    "owner": "Alice",
                    "due_date": "2026-09-16",
                },
                {
                    "description": "追蹤 SPI",
                    "owner": "Bob",
                    "due_date": "2026-09-20",
                },
            ]
        )
        emitted = []
        dialog.action_created.connect(lambda aid: emitted.append(aid))
        with mock.patch.object(
            _case_action_service,
            "create_case_actions_batch",
            return_value=["act-1", "act-2"],
        ) as mk:
            dialog._on_submit()
        mk.assert_called_once_with(
            anomaly_id="anomaly-1",
            items=[
                {
                    "description": "要求 8D",
                    "owner": "Alice",
                    "due_date": "2026-09-16",
                },
                {
                    "description": "追蹤 SPI",
                    "owner": "Bob",
                    "due_date": "2026-09-20",
                },
            ],
            action_type=CASE_ACTION_TYPE_CONTAINMENT,
            execution_status="已規劃",
            verification_required=False,
        )
        self.assertEqual(emitted, ["act-1"])

    def test_empty_description_does_not_call_service(self) -> None:
        dialog = self._dialog()
        with mock.patch.object(
            _case_action_service, "create_case_actions_batch"
        ) as mk:
            dialog._on_submit()
        mk.assert_not_called()


if __name__ == "__main__":
    unittest.main()
