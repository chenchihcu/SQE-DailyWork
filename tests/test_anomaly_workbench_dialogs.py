from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox

from scripts.qt_visual_probe import _set_probe_widget_value
from services.event import _anomaly_workbench_service, _case_action_service
from ui.widgets.anomaly_note_dialog import AnomalyNoteDialog
from ui.widgets.anomaly_root_cause_dialog import AnomalyRootCauseDialog
from ui.widgets.anomaly_hypothesis_dialog import AnomalyHypothesisDialog
from ui.widgets.reopen_anomaly_dialog import ReopenAnomalyDialog
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
        self.assertEqual(mk.call_args.kwargs["content"], "1. 推測為治具磨損")
        self.assertEqual(emitted, ["n-1"])


class AnomalyRootCauseDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_requires_statement_for_verified_status(self) -> None:
        dialog = AnomalyRootCauseDialog("a-1")
        verified_index = dialog.status_combo.findData("已驗證")
        dialog.status_combo.setCurrentIndex(verified_index)
        self.assertFalse(dialog._save_button.isEnabled())
        dialog.statement_input.setPlainText("治具磨損")
        self.assertTrue(dialog._save_button.isEnabled())

    def test_requires_not_established_reason(self) -> None:
        dialog = AnomalyRootCauseDialog("a-1")
        not_established_index = dialog.status_combo.findData("無法確認")
        dialog.status_combo.setCurrentIndex(not_established_index)
        dialog.statement_input.setPlainText("尚無足夠證據")
        self.assertFalse(dialog._save_button.isEnabled())
        dialog.not_established_input.setPlainText("樣本不足")
        self.assertTrue(dialog._save_button.isEnabled())

    def test_submit_calls_save_root_cause(self) -> None:
        dialog = AnomalyRootCauseDialog("a-1")
        dialog.statement_input.setPlainText("治具磨損")
        verified_index = dialog.status_combo.findData("已驗證")
        dialog.status_combo.setCurrentIndex(verified_index)
        dialog.validation_method_input.setPlainText("5-Why")
        emitted = []
        dialog.root_cause_saved.connect(lambda rid: emitted.append(rid))
        with mock.patch.object(
            _anomaly_workbench_service, "save_root_cause", return_value="rc-1"
        ) as mk:
            dialog._on_submit()
        self.assertEqual(mk.call_args.kwargs["statement"], "1. 治具磨損")
        self.assertEqual(mk.call_args.kwargs["status"], "已驗證")
        self.assertEqual(mk.call_args.kwargs["validation_method"], "1. 5-Why")
        self.assertEqual(emitted, ["rc-1"])


class AnomalyHypothesisDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self) -> AnomalyHypothesisDialog:
        with mock.patch.object(
            _anomaly_workbench_service, "list_hypotheses", return_value=[]
        ):
            return AnomalyHypothesisDialog("a-1")

    def test_requires_statement_to_enable_save(self) -> None:
        dialog = self._dialog()
        self.assertFalse(dialog._save_button.isEnabled())
        dialog.statement_input.setPlainText("錫膏回溫不足")
        self.assertTrue(dialog._save_button.isEnabled())

    def test_submit_calls_create_hypothesis(self) -> None:
        dialog = self._dialog()
        dialog.statement_input.setPlainText("治具磨損")
        dialog.evidence_combo.setCurrentIndex(0)
        emitted = []
        dialog.hypothesis_saved.connect(lambda hid: emitted.append(hid))
        with (
            mock.patch.object(
                _anomaly_workbench_service, "list_hypotheses", return_value=[]
            ),
            mock.patch.object(
                _anomaly_workbench_service,
                "create_hypothesis",
                return_value="h-1",
            ) as mk,
        ):
            dialog._on_submit()
        self.assertEqual(mk.call_args.kwargs["statement"], "1. 治具磨損")
        self.assertEqual(emitted, ["h-1"])

    def test_reject_prompts_when_dirty(self) -> None:
        dialog = self._dialog()
        dialog.statement_input.setPlainText("dirty hypothesis")
        with mock.patch.object(dialog, "_confirm_discard", return_value=False) as confirm:
            dialog.reject()
        confirm.assert_called_once()


class ReopenAnomalyDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_reject_prompts_when_dirty(self) -> None:
        dialog = ReopenAnomalyDialog("a-1", ref_no="20260818001")
        dialog.reason_input.setPlainText("need reopen")
        with mock.patch.object(dialog, "_confirm_discard", return_value=False) as confirm:
            dialog.reject()
        confirm.assert_called_once()


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
            _case_action_service, "create_case_action", return_value="ca-1"
        ) as mk:
            dialog._on_submit()
        self.assertEqual(mk.call_args.kwargs["action_type"], "CORRECTIVE_ACTION")
        self.assertTrue(mk.call_args.kwargs["verification_required"])
        self.assertEqual(mk.call_args.kwargs["description"], "1. 更換治具")

    def test_visual_probe_checks_checkbox_without_replacing_its_label(self) -> None:
        checkbox = QCheckBox("需進行有效性驗證")

        _set_probe_widget_value(checkbox, True)

        self.assertTrue(checkbox.isChecked())
        self.assertEqual(checkbox.text(), "需進行有效性驗證")


if __name__ == "__main__":
    unittest.main()
