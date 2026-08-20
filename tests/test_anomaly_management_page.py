from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QScrollArea, QTabWidget, QWidget

from services.event import _anomaly_service, _anomaly_workbench_service
from ui.widgets.anomaly_management_page import AnomalyManagementPage


class AnomalyManagementPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.detail = {
            "anomaly_no": "20260818001",
            "anomaly_date": "2026-08-18",
            "supplier_name": "測試供應商",
            "product_name": "測試產品",
            "product_code": "P-001",
            "category": "外觀",
            "batch_qty": 2,
            "problem_desc": "測試異常",
            "status": "待處理",
        }
        self.overview = {
            "current_action": None,
            "overdue": False,
        }
        self.patchers = [
            mock.patch.object(_anomaly_service, "get_anomaly_detail", return_value=self.detail),
            mock.patch.object(_anomaly_workbench_service, "get_overview_card", return_value=self.overview),
            mock.patch.object(_anomaly_workbench_service, "list_timeline", return_value=[]),
            mock.patch.object(_anomaly_workbench_service, "list_analysis_notes", return_value=[]),
            mock.patch.object(_anomaly_workbench_service, "get_root_cause", return_value=None),
            mock.patch.object(_anomaly_workbench_service, "list_eight_d_reviews", return_value=[]),
            mock.patch.object(_anomaly_workbench_service, "list_corrective_actions", return_value=[]),
            mock.patch.object(_anomaly_workbench_service, "list_attachments", return_value=[]),
            mock.patch.object(_anomaly_workbench_service, "list_audit_logs", return_value=[]),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in self.patchers:
            patcher.stop()

    def test_renders_seven_management_tabs(self) -> None:
        page = AnomalyManagementPage(mock.Mock())
        page.load_anomaly("anomaly-1")

        tabs = page.findChild(QTabWidget, "AnomalyManagementTabs")
        self.assertIsNotNone(tabs)
        self.assertEqual(tabs.count(), 7)
        self.assertEqual(
            [tabs.tabText(index) for index in range(tabs.count())],
            list(AnomalyManagementPage.TAB_NAMES),
        )

    def test_loads_anomaly_and_enters_inline_edit(self) -> None:
        page = AnomalyManagementPage(mock.Mock())
        page.load_anomaly("anomaly-1", edit=True)

        self.assertIsNotNone(page._edit_form)
        self.assertTrue(page._editing)
        self.assertIsInstance(page.tabs.widget(0), QWidget)
        self.assertFalse(page.save_button.isHidden())
        self.assertFalse(page.cancel_button.isHidden())

    def test_dirty_form_blocks_leave(self) -> None:
        page = AnomalyManagementPage(mock.Mock())
        page.load_anomaly("anomaly-1", edit=True)
        assert page._edit_form is not None
        page._edit_form._dirty = True
        with mock.patch.object(page._edit_form, "_confirm_discard", return_value=False):
            self.assertFalse(page.can_leave())

    def test_each_management_tab_has_one_visible_scroll_owner(self) -> None:
        page = AnomalyManagementPage(mock.Mock())
        page.load_anomaly("anomaly-1")

        for index in range(page.tabs.count()):
            tab = page.tabs.widget(index)
            scrolls = tab.findChildren(QScrollArea)
            self.assertEqual(1, len(scrolls))
            self.assertTrue(scrolls[0].widgetResizable())

    def test_command_buttons_follow_save_then_cancel_order(self) -> None:
        page = AnomalyManagementPage(mock.Mock())
        command_row = page.layout().itemAt(3).layout()

        self.assertIs(command_row.itemAt(1).widget(), page.save_button)
        self.assertIs(command_row.itemAt(2).widget(), page.cancel_button)
        self.assertEqual(page.save_button.accessibleName(), "儲存異常")
        self.assertEqual(page.cancel_button.accessibleName(), "取消編輯")


if __name__ == "__main__":
    unittest.main()
