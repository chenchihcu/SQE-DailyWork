from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton, QScrollArea, QTabWidget, QWidget

from services.event import (
    _anomaly_service,
    _anomaly_workbench_service,
    _case_action_service,
)
from services import repeat_issue_service
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
            "root_cause_status": "尚未開始",
            "corrective_action_status": "—",
            "verification_result": "—",
            "hypothesis_count": 0,
            "hypothesis_deepest_level": 0,
        }
        self.patchers = [
            mock.patch.object(_anomaly_service, "get_anomaly_detail", return_value=self.detail),
            mock.patch.object(_anomaly_workbench_service, "get_overview_card", return_value=self.overview),
            mock.patch.object(_anomaly_workbench_service, "list_timeline", return_value=[]),
            mock.patch.object(_anomaly_workbench_service, "list_analysis_notes", return_value=[]),
            mock.patch.object(_anomaly_workbench_service, "list_hypotheses", return_value=[]),
            mock.patch.object(_anomaly_workbench_service, "get_root_cause", return_value=None),
            mock.patch.object(_anomaly_workbench_service, "list_eight_d_reviews", return_value=[]),
            mock.patch.object(_case_action_service, "list_case_actions", return_value=[]),
            mock.patch.object(
                _anomaly_workbench_service, "list_attachment_actions", return_value=[]
            ),
            mock.patch.object(_anomaly_workbench_service, "list_attachments", return_value=[]),
            mock.patch.object(_anomaly_workbench_service, "list_audit_logs", return_value=[]),
            mock.patch.object(repeat_issue_service, "list_repeat_issues", return_value=[]),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in self.patchers:
            patcher.stop()
        app = QApplication.instance()
        if app is not None:
            for widget in list(app.topLevelWidgets()):
                widget.close()
                widget.deleteLater()
            app.processEvents()

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

    def test_analysis_tab_exposes_hypothesis_actions(self) -> None:
        page = AnomalyManagementPage(mock.Mock())
        page.load_anomaly("anomaly-1")
        analysis_tab = page.tabs.widget(2)
        buttons = [
            child.text()
            for child in analysis_tab.findChildren(QPushButton)
        ]
        self.assertIn("新增假設", buttons)
        self.assertIn("編輯假設", buttons)
        self.assertIn("晉升為根本原因", buttons)

    def test_command_buttons_follow_save_then_cancel_order(self) -> None:
        page = AnomalyManagementPage(mock.Mock())
        command_row = page.layout().itemAt(4).layout()

        self.assertIs(command_row.itemAt(1).widget(), page.save_button)
        self.assertIs(command_row.itemAt(2).widget(), page.cancel_button)
        self.assertEqual(page.save_button.accessibleName(), "儲存異常")
        self.assertEqual(page.cancel_button.accessibleName(), "取消編輯")

    def test_header_close_and_reopen_buttons_are_mutually_exclusive(self) -> None:
        page = AnomalyManagementPage(mock.Mock())
        page.load_anomaly("anomaly-1")
        self.assertTrue(page.close_button.isEnabled())
        self.assertFalse(page.reopen_button.isEnabled())
        self.assertTrue(page.edit_button.isEnabled())

        self.detail["status"] = "已結案"
        page.load_anomaly("anomaly-1")
        self.assertFalse(page.close_button.isEnabled())
        self.assertTrue(page.reopen_button.isEnabled())
        self.assertFalse(page.edit_button.isEnabled())

    def test_overview_tab_exposes_quality_conclusion_section(self) -> None:
        page = AnomalyManagementPage(mock.Mock())
        page.load_anomaly("anomaly-1")
        overview_tab = page.tabs.widget(0)
        labels = [
            child.text()
            for child in overview_tab.findChildren(type(page.header_text))
            if child.property("role") == "sectionTitle"
        ]
        self.assertIn("品質結論", labels)
        self.assertIn("案件資料", labels)
        self.assertIn("目前處置", labels)

    def test_closed_case_disables_corrective_action_commands(self) -> None:
        action = {
            "id": "action-1",
            "action_type": "CORRECTIVE_ACTION",
            "action_type_label": "改善措施",
            "description": "test",
            "execution_status": "已規劃",
            "verification_required": False,
            "verification_status": "不需要",
            "owner": "SQE",
            "due_date": "2026-09-01",
        }
        with mock.patch.object(
            _case_action_service, "list_case_actions", return_value=[action]
        ):
            page = AnomalyManagementPage(mock.Mock())
            page.load_anomaly("anomaly-1")
            corrective_tab = page.tabs.widget(4)
            buttons = [btn.text() for btn in corrective_tab.findChildren(QPushButton)]
            self.assertIn("開始執行", buttons)

            self.detail["status"] = "已結案"
            page.load_anomaly("anomaly-1")
            corrective_tab = page.tabs.widget(4)
            buttons = [btn.text() for btn in corrective_tab.findChildren(QPushButton)]
            self.assertNotIn("開始執行", buttons)
            self.assertNotIn("完成／取消", buttons)

            analysis_tab = page.tabs.widget(2)
            analysis_buttons = [
                btn.text() for btn in analysis_tab.findChildren(QPushButton)
            ]
            self.assertIn("新增分析紀錄", analysis_buttons)
            add_note = next(
                btn
                for btn in analysis_tab.findChildren(QPushButton)
                if btn.text() == "新增分析紀錄"
            )
            self.assertTrue(add_note.isEnabled())

    def test_verification_button_hidden_after_result_recorded(self) -> None:
        pending_action = {
            "id": "action-1",
            "action_type": "CORRECTIVE_ACTION",
            "action_type_label": "改善措施",
            "description": "test",
            "execution_status": "已完成",
            "verification_required": True,
            "verification_status": "待驗證",
            "owner": "SQE",
            "due_date": "2026-09-01",
        }
        verified_action = {
            **pending_action,
            "verification_status": "有效",
        }
        with mock.patch.object(
            _case_action_service,
            "list_case_actions",
            side_effect=[[pending_action], [verified_action]],
        ):
            page = AnomalyManagementPage(mock.Mock())
            page.load_anomaly("anomaly-1")
            corrective_tab = page.tabs.widget(4)
            buttons = [btn.text() for btn in corrective_tab.findChildren(QPushButton)]
            self.assertIn("新增有效性驗證", buttons)

            page.load_anomaly("anomaly-1")
            corrective_tab = page.tabs.widget(4)
            buttons = [btn.text() for btn in corrective_tab.findChildren(QPushButton)]
            self.assertNotIn("新增有效性驗證", buttons)

    def test_repeat_issues_panel_survives_runtime_error(self) -> None:
        with mock.patch.object(
            repeat_issue_service,
            "list_repeat_issues",
            side_effect=RuntimeError("schema not ready"),
        ):
            page = AnomalyManagementPage(mock.Mock())
            page.load_anomaly("anomaly-1")
            self.assertEqual(0, page.repeat_issues_panel._table.rowCount())


if __name__ == "__main__":
    unittest.main()
