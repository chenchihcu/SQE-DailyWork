from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from ui.widgets.new_anomaly_dialog import NewAnomalyDialog
from ui.widgets.event_actions import (
    ACTION_VIEW_ANOMALY_DETAILS,
    build_event_action_menu,
)

class EventPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            pass  # do not terminate shared QApplication singleton in test runner

    def test_anomaly_menu_contains_case_details(self):
        row = {"event_type": "ANOMALY", "status": "待處理", "linked_visit_id": ""}
        menu, action_map = build_event_action_menu(None, row)
        actions = [a.text() for a in menu.actions()]
        self.assertIn("案件詳情", actions)
        details_action = [a for a in menu.actions() if a.text() == "案件詳情"][0]
        self.assertEqual(action_map[details_action], ACTION_VIEW_ANOMALY_DETAILS)

    @patch("services.event_service.list_active_suppliers", return_value=[])
    def test_anomaly_dialog_read_only_mode(self, mock_suppliers):
        dialog = NewAnomalyDialog(read_only=True)
        self.assertFalse(dialog.date_edit.isEnabled())
        self.assertFalse(dialog.supplier_combo.isEnabled())
        self.assertTrue(dialog.problem_input.isReadOnly())
        self.assertEqual(dialog.save_button.text(), "關閉")
        self.assertFalse(dialog.attachment_editor.add_button.isEnabled())

if __name__ == "__main__":
    unittest.main()
