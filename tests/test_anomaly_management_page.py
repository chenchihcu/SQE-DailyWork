from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QWidget,
)

from ui.widgets.anomaly_action_table import AnomalyActionTable

from services.event import (
    _anomaly_service,
    _anomaly_workbench_service,
    _case_action_service,
)
from services import repeat_issue_service
from ui.sidebar_nav import PAGE_EVENT_OVERDUE
from ui.widgets.anomaly_management_page import AnomalyManagementPage
from ui.widgets.anomaly_photo_thumb_grid import ProblemEvidenceOverviewPanel
from ui.widgets.common_widgets import CaseStageStepper


class AnomalyManagementPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls._host = QWidget()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._host.close()
        cls._host.deleteLater()
        app = QApplication.instance()
        if app is not None:
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()

    def setUp(self) -> None:
        self._pages: list[AnomalyManagementPage] = []
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
            mock.patch.object(_anomaly_workbench_service, "get_root_cause", return_value=None),
            mock.patch.object(_case_action_service, "list_case_actions", return_value=[]),
            mock.patch.object(
                _anomaly_workbench_service, "list_attachment_actions", return_value=[]
            ),
            mock.patch.object(
                _anomaly_workbench_service, "list_attachment_notes", return_value=[]
            ),
            mock.patch.object(
                _anomaly_workbench_service, "list_attachment_hypotheses", return_value=[]
            ),
            mock.patch.object(_anomaly_workbench_service, "list_attachments", return_value=[]),
            mock.patch.object(repeat_issue_service, "list_repeat_issues", return_value=[]),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in self.patchers:
            patcher.stop()
        for page in self._pages:
            page.close()
            page.deleteLater()
        self._pages.clear()
        app = QApplication.instance()
        if app is not None:
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()

    def _make_page(self) -> AnomalyManagementPage:
        page = AnomalyManagementPage(self._host)
        self._pages.append(page)
        return page

    def test_renders_four_management_tabs(self) -> None:
        page = self._make_page()
        page.load_anomaly("anomaly-1")

        tabs = page.findChild(QTabWidget, "AnomalyManagementTabs")
        self.assertIsNotNone(tabs)
        self.assertEqual(tabs.count(), 4)
        self.assertEqual(
            [tabs.tabText(index) for index in range(tabs.count())],
            list(AnomalyManagementPage.TAB_NAMES),
        )
        self.assertFalse(tabs.tabBar().expanding())

    def test_initial_tab_selects_named_workbench_tab(self) -> None:
        page = self._make_page()
        page.load_anomaly("anomaly-1", initial_tab="Action 清單")
        tabs = page.findChild(QTabWidget, "AnomalyManagementTabs")
        self.assertIsNotNone(tabs)
        self.assertEqual(1, tabs.currentIndex())
        self.assertEqual("Action 清單", tabs.tabText(tabs.currentIndex()))

    def test_stage_stepper_not_present(self) -> None:
        page = self._make_page()
        page.load_anomaly("anomaly-1")
        self.assertIsNone(page.findChild(CaseStageStepper, "CaseStageStepper"))

    def test_loads_anomaly_and_enters_inline_edit(self) -> None:
        page = self._make_page()
        page.load_anomaly("anomaly-1", edit=True)

        self.assertIsNotNone(page._edit_form)
        self.assertTrue(page._editing)
        self.assertIsInstance(page.tabs.widget(0), QWidget)
        self.assertFalse(page.save_button.isHidden())
        self.assertFalse(page.cancel_button.isHidden())

    def test_dirty_form_blocks_leave(self) -> None:
        page = self._make_page()
        page.load_anomaly("anomaly-1", edit=True)
        assert page._edit_form is not None
        page._edit_form._dirty = True
        with mock.patch.object(page._edit_form, "_confirm_discard", return_value=False):
            self.assertFalse(page.can_leave())

    def test_each_management_tab_has_one_visible_scroll_owner(self) -> None:
        page = self._make_page()
        page.load_anomaly("anomaly-1")

        for index in range(page.tabs.count()):
            tab = page.tabs.widget(index)
            scrolls = tab.findChildren(QScrollArea)
            self.assertEqual(1, len(scrolls))
            self.assertTrue(scrolls[0].widgetResizable())

    def test_overview_tab_exposes_case_and_problem_evidence_sections(self) -> None:
        page = self._make_page()
        page.load_anomaly("anomaly-1")
        overview_tab = page.tabs.widget(0)
        labels = [
            child.text()
            for child in overview_tab.findChildren(QLabel)
            if child.property("role") == "sectionTitle"
        ]
        self.assertEqual(["案件概覽", "不良現象與現場照片"], labels)
        panel = overview_tab.findChild(
            ProblemEvidenceOverviewPanel, "ProblemEvidenceOverviewPanel"
        )
        self.assertIsNotNone(panel)

    def test_overview_view_all_attachments_switches_tab(self) -> None:
        page = self._make_page()
        page.load_anomaly("anomaly-1")
        overview_tab = page.tabs.widget(0)
        panel = overview_tab.findChild(
            ProblemEvidenceOverviewPanel, "ProblemEvidenceOverviewPanel"
        )
        self.assertIsNotNone(panel)
        panel.view_all_requested.emit()
        self.assertEqual(3, page.tabs.currentIndex())
        self.assertEqual("附件與佐證", page.tabs.tabText(page.tabs.currentIndex()))

    def test_root_cause_tab_exposes_investigation_sections(self) -> None:
        page = self._make_page()
        page.load_anomaly("anomaly-1")
        root_cause_tab = page.tabs.widget(2)
        labels = [
            child.text()
            for child in root_cause_tab.findChildren(QLabel)
            if child.property("role") == "sectionTitle"
        ]
        self.assertIn("調查與根本原因", labels)
        self.assertNotIn("調查進度", labels)
        buttons = [child.text() for child in root_cause_tab.findChildren(QPushButton)]
        self.assertIn("編輯根本原因", buttons)
        self.assertNotIn("新增分析紀錄", buttons)
        self.assertNotIn("新增假設", buttons)

    def test_root_cause_tab_renders_full_read_model(self) -> None:
        page = self._make_page()
        root_cause = {
            "status": "已驗證",
            "statement": "1. 治具磨損",
            "validation_method": "1. 5-Why",
            "validation_evidence": "1. 現場量測",
            "conclusion_note": "1. 高信心",
            "not_established_reason": "",
        }
        with mock.patch.object(
            _anomaly_workbench_service, "get_root_cause", return_value=root_cause
        ):
            page.load_anomaly("anomaly-1")
        root_cause_tab = page.tabs.widget(2)
        rendered = [
            child.text()
            for child in root_cause_tab.findChildren(QLabel)
            if child.property("role") == "value"
        ]
        joined = "\n".join(rendered)
        self.assertIn("狀態：已驗證", joined)
        self.assertIn("說明：1. 治具磨損", joined)
        self.assertIn("驗證方式：1. 5-Why", joined)
        self.assertIn("驗證證據：1. 現場量測", joined)
        self.assertIn("結論說明：1. 高信心", joined)
        self.assertNotIn("無法確認原因", joined)

    def test_actions_tab_exposes_action_table(self) -> None:
        page = self._make_page()
        page.load_anomaly("anomaly-1")
        actions_tab = page.tabs.widget(1)
        self.assertIsNone(actions_tab.findChild(AnomalyActionTable, "AnomalyActionTable"))
        buttons = [child.text() for child in actions_tab.findChildren(QPushButton)]
        self.assertIn("新增 Action", buttons)

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
            page.load_anomaly("anomaly-1")
            actions_tab = page.tabs.widget(1)
            table = actions_tab.findChild(AnomalyActionTable, "AnomalyActionTable")
            self.assertIsNotNone(table)
            self.assertEqual(list(AnomalyActionTable.TABLE_HEADERS), [
                table.horizontalHeaderItem(index).text()
                for index in range(table.columnCount())
            ])
            self.assertIsNotNone(table.item(0, AnomalyActionTable.COL_DESC))
            buttons = [child.text() for child in actions_tab.findChildren(QPushButton)]
            self.assertIn("編輯", buttons)
            accessible = [
                child.accessibleName()
                for child in actions_tab.findChildren(QPushButton)
            ]
            self.assertTrue(any(name.startswith("編輯 Action") for name in accessible))
            self.assertTrue(any(name.startswith("取消 Action") for name in accessible))

    def test_command_buttons_follow_save_then_cancel_order(self) -> None:
        page = self._make_page()
        command_row = page.layout().itemAt(2).layout()

        self.assertIs(command_row.itemAt(1).widget(), page.save_button)
        self.assertIs(command_row.itemAt(2).widget(), page.cancel_button)
        self.assertEqual(page.save_button.accessibleName(), "儲存異常")
        self.assertEqual(page.cancel_button.accessibleName(), "取消編輯")

    def test_header_close_and_reopen_buttons_are_mutually_exclusive(self) -> None:
        page = self._make_page()
        page.load_anomaly("anomaly-1")
        self.assertFalse(page.close_button.isHidden())
        self.assertTrue(page.reopen_button.isHidden())
        self.assertTrue(page.edit_button.isEnabled())

        self.detail["status"] = "已結案"
        page.load_anomaly("anomaly-1")
        self.assertTrue(page.close_button.isHidden())
        self.assertFalse(page.reopen_button.isHidden())
        self.assertFalse(page.edit_button.isEnabled())

    def test_empty_fields_hidden_in_overview_grid(self) -> None:
        page = self._make_page()
        page.load_anomaly("anomaly-1")
        overview_tab = page.tabs.widget(0)
        value_labels = [
            child.text()
            for child in overview_tab.findChildren(QLabel)
            if child.property("role") == "value"
        ]
        self.assertFalse(any(text.startswith("來源 NCR 單號：") for text in value_labels))
        self.assertFalse(any(text.startswith("SMT 製程關鍵詞：") for text in value_labels))

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
            page = self._make_page()
            page.load_anomaly("anomaly-1")
            actions_tab = page.tabs.widget(1)
            buttons = [btn.text() for btn in actions_tab.findChildren(QPushButton)]
            self.assertIn("開始執行", buttons)

            self.detail["status"] = "已結案"
            page.load_anomaly("anomaly-1")
            actions_tab = page.tabs.widget(1)
            buttons = [btn.text() for btn in actions_tab.findChildren(QPushButton)]
            self.assertNotIn("開始執行", buttons)
            self.assertNotIn("完成", buttons)
            self.assertNotIn("取消", buttons)
            self.assertIn("新增 Action", buttons)

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
            page = self._make_page()
            page.load_anomaly("anomaly-1")
            actions_tab = page.tabs.widget(1)
            buttons = [btn.text() for btn in actions_tab.findChildren(QPushButton)]
            self.assertIn("新增有效性驗證", buttons)

            page.load_anomaly("anomaly-1")
            actions_tab = page.tabs.widget(1)
            buttons = [btn.text() for btn in actions_tab.findChildren(QPushButton)]
            self.assertNotIn("新增有效性驗證", buttons)

    def test_footer_command_row_has_only_save_and_cancel(self) -> None:
        page = self._make_page()
        page.load_anomaly("anomaly-1")
        command_row = page.layout().itemAt(2).layout()
        footer_buttons = [
            command_row.itemAt(index).widget()
            for index in range(command_row.count())
            if command_row.itemAt(index).widget() is not None
        ]
        self.assertEqual([page.save_button, page.cancel_button], footer_buttons)
        close_buttons = [
            button for button in page.findChildren(QPushButton) if button.text() == "結案"
        ]
        reopen_buttons = [
            button
            for button in page.findChildren(QPushButton)
            if button.text() == "重新開啟"
        ]
        self.assertEqual(1, len(close_buttons))
        self.assertEqual(1, len(reopen_buttons))
        self.assertIs(close_buttons[0], page.close_button)
        self.assertIs(reopen_buttons[0], page.reopen_button)

    def test_return_to_list_opens_ops_queue_when_source_is_ops_family(self) -> None:
        main_window = mock.Mock()
        main_window._workbench_source_page_key = PAGE_EVENT_OVERDUE
        page = AnomalyManagementPage(main_window)
        self._pages.append(page)
        page.load_anomaly("anomaly-1")
        self.assertEqual("返回作業佇列", page.back_button.text())
        page.return_to_list()
        main_window.open_supplier_event_ops.assert_called_once_with(PAGE_EVENT_OVERDUE)

    def test_repeat_button_survives_runtime_error(self) -> None:
        with mock.patch.object(
            repeat_issue_service,
            "list_repeat_issues",
            side_effect=RuntimeError("schema not ready"),
        ):
            page = self._make_page()
            page.load_anomaly("anomaly-1")
            self.assertEqual("潛在重複 (0)", page.repeat_button.text())

    def test_repeat_button_opens_dedicated_repeat_page(self) -> None:
        main_window = mock.Mock()
        page = AnomalyManagementPage(main_window)
        self._pages.append(page)
        with mock.patch.object(
            repeat_issue_service,
            "list_repeat_issues",
            return_value=[{"peer_anomaly_id": "aid-2", "similarity_score": 80}],
        ):
            page.load_anomaly("anomaly-1")
            self.assertEqual("潛在重複 (1)", page.repeat_button.text())
            page.repeat_button.click()
            main_window.open_repeat_issues_management.assert_called_once_with("anomaly-1")


if __name__ == "__main__":
    unittest.main()
