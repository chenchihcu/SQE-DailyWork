from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from services.event import (
    _anomaly_workbench_service,
    _case_action_service,
)
from ui.widgets.add_audit_log_dialog import AddAuditLogDialog
from ui.widgets.add_eight_d_review_dialog import AddEightDReviewDialog
from ui.widgets.add_verification_dialog import AddVerificationDialog
from ui.widgets.complete_action_dialog import CompleteActionDialog


class CompleteActionDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_completes_open_action(self) -> None:
        dialog = CompleteActionDialog("a-1", action_summary="Send 8D")
        dialog.note_input.setPlainText("submitted to supplier")
        emitted = []
        dialog.action_updated.connect(lambda v: emitted.append(v))
        with mock.patch.object(
            _case_action_service, "complete_case_action"
        ) as mk:
            dialog._on_submit()
        self.assertEqual(mk.call_args.args[0], "a-1")
        self.assertEqual(mk.call_args.kwargs["completion_note"], "1. submitted to supplier")
        self.assertEqual(emitted, ["a-1"])

    def test_cancels_open_action(self) -> None:
        dialog = CompleteActionDialog("a-2")
        dialog.outcome_combo.setCurrentIndex(1)
        dialog.note_input.setPlainText("duplicate of #3")
        with mock.patch.object(
            _case_action_service, "cancel_case_action"
        ) as mk:
            dialog._on_submit()
        self.assertEqual(mk.call_args.args[0], "a-2")
        self.assertEqual(mk.call_args.kwargs["cancel_note"], "1. duplicate of #3")


class AddVerificationDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_requires_method(self) -> None:
        dialog = AddVerificationDialog("ca-1")
        self.assertFalse(dialog._save_button.isEnabled())
        dialog.method_input.setText("30 天監控")
        self.assertTrue(dialog._save_button.isEnabled())

    def test_passes_verification_payload(self) -> None:
        dialog = AddVerificationDialog("ca-2", description="製程改善")
        dialog.method_input.setText("30 天監控")
        dialog.criteria_input.setText("NG 率 < 0.5%")
        dialog.sample_input.setText("3 批")
        dialog.result_combo.setCurrentIndex(1)  # 有效
        dialog.evidence_input.setPlainText("三批皆合格")
        dialog.conclusion_input.setPlainText("可結案")
        dialog.verified_by_input.setText("王五")
        emitted = []
        dialog.verification_created.connect(lambda v: emitted.append(v))
        with mock.patch.object(
            _case_action_service,
            "record_action_verification",
            return_value="v-1",
        ) as mk:
            dialog._on_submit()
        kwargs = mk.call_args.kwargs
        self.assertEqual(kwargs["action_id"], "ca-2")
        self.assertEqual(kwargs["method"], "30 天監控")
        self.assertEqual(kwargs["result"], "有效")
        self.assertEqual(kwargs["verified_by"], "王五")
        self.assertEqual(emitted, ["v-1"])


class AddEightDReviewDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_requires_revision(self) -> None:
        dialog = AddEightDReviewDialog("an-1")
        self.assertFalse(dialog._save_button.isEnabled())
        dialog.revision_input.setText("Rev A")
        self.assertTrue(dialog._save_button.isEnabled())

    def test_appends_review_with_audit(self) -> None:
        dialog = AddEightDReviewDialog("an-1", next_revision_hint="Rev A")
        dialog.status_combo.setCurrentIndex(0)  # 接受
        dialog.comment_input.setPlainText("已補齊")
        emitted = []
        dialog.review_created.connect(lambda v: emitted.append(v))
        with mock.patch.object(
            _anomaly_workbench_service,
            "create_eight_d_review_with_audit",
            return_value=("rev-1", "audit-1"),
        ) as mk:
            dialog._on_submit()
        kwargs = mk.call_args.kwargs
        self.assertEqual(kwargs["anomaly_id"], "an-1")
        self.assertEqual(kwargs["revision"], "Rev A")
        self.assertEqual(kwargs["review_status"], "接受")
        self.assertEqual(kwargs["review_comment"], "1. 已補齊")
        self.assertEqual(emitted, ["rev-1"])


class AddAuditLogDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_requires_action_and_message(self) -> None:
        dialog = AddAuditLogDialog("an-1")
        dialog.message_input.setPlainText("與供應商電話會議")
        # action combo has default index 0 (NOTE) so both fields are filled.
        self.assertTrue(dialog._save_button.isEnabled())
        # clearing message disables save; setting action kind via text also enables
        dialog.message_input.setPlainText("")
        self.assertFalse(dialog._save_button.isEnabled())
        dialog.action_combo.setCurrentText("MEETING")
        dialog.message_input.setPlainText("再次與供應商確認")
        self.assertTrue(dialog._save_button.isEnabled())

    def test_appends_manual_audit(self) -> None:
        dialog = AddAuditLogDialog("an-1")
        dialog.action_combo.setCurrentText("MEETING")
        dialog.message_input.setPlainText("與供應商電話會議")
        emitted = []
        dialog.audit_created.connect(lambda v: emitted.append(v))
        with mock.patch.object(
            _anomaly_workbench_service,
            "append_manual_audit",
            return_value="audit-1",
        ) as mk:
            dialog._on_submit()
        kwargs = mk.call_args.kwargs
        self.assertEqual(kwargs["anomaly_id"], "an-1")
        self.assertEqual(kwargs["action"], "MEETING")
        self.assertEqual(kwargs["after_value"], "1. 與供應商電話會議")
        self.assertEqual(emitted, ["audit-1"])


if __name__ == "__main__":
    unittest.main()
