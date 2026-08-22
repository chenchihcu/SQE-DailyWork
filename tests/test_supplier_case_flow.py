from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.widgets.common_widgets import CaseStageStepper


class SupplierCaseFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_case_stage_stepper_has_six_read_only_stages(self) -> None:
        stepper = CaseStageStepper()
        overview = {
            "current_action": {"description": "追蹤"},
            "root_cause_status": "已驗證",
            "corrective_action_status": "已實施",
            "verification_result": "有效",
        }
        stepper.set_case_state(
            {
                "status": "已結案",
                "pending_items": "確認",
            },
            overview,
        )
        self.assertEqual(6, len(stepper._labels))
        self.assertTrue(
            all(label.property("role") == "stageComplete" for label in stepper._labels)
        )

    def test_root_cause_not_started_does_not_complete_root_stage(self) -> None:
        stepper = CaseStageStepper()
        overview = {
            "current_action": {"description": "追蹤"},
            "root_cause_status": "尚未開始",
            "corrective_action_status": "—",
            "verification_result": "—",
        }
        stepper.set_case_state({"status": "待處理"}, overview)
        self.assertEqual("stageComplete", stepper._labels[0].property("role"))
        self.assertEqual("stageComplete", stepper._labels[1].property("role"))
        self.assertEqual("stagePending", stepper._labels[2].property("role"))


if __name__ == "__main__":
    unittest.main()
