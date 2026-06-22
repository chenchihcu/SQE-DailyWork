from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from ui.widgets.defect_form_widget import NewAnomalyDialog, NewVisitDialog
from ui.widgets.event_actions import build_event_action_menu, ACTION_PREVIEW_ANOMALY, ACTION_PREVIEW_VISIT

class EventPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

    def test_anomaly_menu_contains_preview(self):
        row = {"event_type": "ANOMALY", "status": "待處理", "linked_visit_id": ""}
        menu, action_map = build_event_action_menu(None, row)
        actions = [a.text() for a in menu.actions()]
        self.assertIn("預覽內容", actions)
        
        # Verify action mapping
        preview_action = [a for a in menu.actions() if a.text() == "預覽內容"][0]
        self.assertEqual(action_map[preview_action], ACTION_PREVIEW_ANOMALY)

    def test_visit_menu_contains_preview(self):
        row = {"event_type": "VISIT"}
        menu, action_map = build_event_action_menu(None, row)
        actions = [a.text() for a in menu.actions()]
        self.assertIn("預覽內容", actions)
        
        preview_action = [a for a in menu.actions() if a.text() == "預覽內容"][0]
        self.assertEqual(action_map[preview_action], ACTION_PREVIEW_VISIT)

    @patch("ui.widgets.defect_form_widget.event_service.list_active_suppliers", return_value=[])
    def test_anomaly_dialog_read_only_mode(self, mock_suppliers):
        dialog = NewAnomalyDialog(read_only=True)
        # Check some key widgets
        self.assertFalse(dialog.date_edit.isEnabled())
        self.assertFalse(dialog.supplier_combo.isEnabled())
        self.assertTrue(dialog.problem_input.isReadOnly())
        self.assertEqual(dialog.save_button.text(), "關閉")
        self.assertFalse(dialog.attachment_editor.add_button.isEnabled())

    @patch("ui.widgets.defect_form_widget.event_service.list_active_suppliers", return_value=[])
    def test_visit_dialog_read_only_mode(self, mock_suppliers):
        dialog = NewVisitDialog(read_only=True)
        self.assertFalse(dialog.date_edit.isEnabled())
        self.assertTrue(dialog.summary_input.isReadOnly())
        self.assertEqual(dialog.save_button.text(), "關閉")

if __name__ == "__main__":
    unittest.main()
