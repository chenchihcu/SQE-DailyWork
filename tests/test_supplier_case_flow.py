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
        stepper.set_case_state(
            {
                "status": "已結案",
                "pending_items": "確認",
                "root_cause_status": "已完成",
                "corrective_action_status": "已完成",
                "verification_result": "有效",
            }
        )
        self.assertEqual(6, len(stepper._labels))
        self.assertTrue(
            all(label.property("role") == "stageComplete" for label in stepper._labels)
        )


if __name__ == "__main__":
    unittest.main()
