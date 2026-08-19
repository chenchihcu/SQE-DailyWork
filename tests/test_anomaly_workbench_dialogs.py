from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from services.event import _anomaly_workbench_service
from ui.widgets.anomaly_note_dialog import AnomalyNoteDialog
from ui.widgets.add_corrective_action_dialog import AddCorrectiveActionDialog


class AnomalyNoteDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_requires_content_to_enable_save(self) -> None:
        dialog = AnomalyNoteDialog("a-1")
        self.assertFalse(dialog._save_button.isEnabled())
        dialog.content_input.setPlainText("確認烘烤溫度")
        self.assertTrue(dialog._save_button.isEnabled())

    def test_submit_sends_evidence_value(self) -> None:
        dialog = AnomalyNoteDialog("a-1")
        dialog.content_input.setPlainText("推測為治具磨損")
        dialog.evidence_combo.setCurrentIndex(1)  # INFERENCE
        emitted = []
        dialog.note_created.connect(lambda nid: emitted.append(nid))
        with mock.patch.object(
            _anomaly_workbench_service, "create_analysis_note", return_value="n-1"
        ) as mk:
            dialog._on_submit()
        self.assertEqual(mk.call_args.kwargs["evidence_type"], "INFERENCE")
        self.assertEqual(mk.call_args.kwargs["content"], "推測為治具磨損")
        self.assertEqual(emitted, ["n-1"])


class AddCorrectiveActionDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_requires_description(self) -> None:
        dialog = AddCorrectiveActionDialog("a-1")
        self.assertFalse(dialog._save_button.isEnabled())
        dialog.description_input.setPlainText("更換治具")
        self.assertTrue(dialog._save_button.isEnabled())

    def test_submit_sends_verification_flag(self) -> None:
        dialog = AddCorrectiveActionDialog("a-1")
        dialog.description_input.setPlainText("更換治具")
        dialog.verify_check.setChecked(True)
        with mock.patch.object(
            _anomaly_workbench_service, "create_corrective_action", return_value="ca-1"
        ) as mk:
            dialog._on_submit()
        self.assertTrue(mk.call_args.kwargs["effectiveness_verification_required"])
        self.assertEqual(mk.call_args.kwargs["description"], "更換治具")


if __name__ == "__main__":
    unittest.main()
