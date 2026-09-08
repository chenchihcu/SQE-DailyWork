"""Tests for RepeatIssuesManagementPage."""

from __future__ import annotations

import os
import sys
from pathlib import Path
import unittest
from unittest import mock

SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import tests  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QWidget

from services import repeat_issue_service
from services.event import _anomaly_service, _anomaly_workbench_service
from ui.widgets.repeat_issues_management_page import RepeatIssuesManagementPage


class RepeatIssuesManagementPageTests(unittest.TestCase):
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
        self._pages: list[RepeatIssuesManagementPage] = []
        self.mock_main_window = mock.MagicMock(spec=QWidget)
        self.mock_main_window.open_anomaly_management = mock.MagicMock()
        self.mock_main_window.return_to_event_list = mock.MagicMock()
        self.source_detail = {
            "id": "aid-1",
            "anomaly_no": "20260629001",
            "anomaly_date": "2026-06-29",
            "supplier_id": "sid-1",
            "supplier_name": "拓實光電",
            "product_name": "SMT製程板",
            "product_code": "P-001",
            "category": "製程參數失控",
            "problem_desc": "爐溫均溫沒有管制，點之間溫差大",
            "status": "待處理",
            "improvement_desc": "改善說明待填寫",
        }
        self.peer_detail = {
            "id": "aid-2",
            "anomaly_no": "20260323001",
            "anomaly_date": "2026-03-23",
            "supplier_id": "sid-1",
            "supplier_name": "拓實光電",
            "product_name": "SMT製程板",
            "product_code": "P-001",
            "category": "製程參數失控",
            "problem_desc": "迴焊爐溫異常偏低",
            "status": "已結案",
            "improvement_desc": "更換加熱管並重測溫升曲線",
        }
        self.mock_repeat_rows = [
            {
                "peer_anomaly_id": "aid-2",
                "similarity_score": 75,
                "match_reasons": "相同異常類別、相同料號產品",
                "anomaly_no": "20260323001",
                "anomaly_date": "2026-03-23",
                "category": "製程參數失控",
                "status": "已結案",
                "product_name": "SMT製程板",
                "problem_desc": "迴焊爐溫異常偏低",
                "disposition": "待確認",
            }
        ]

    def tearDown(self) -> None:
        for p in self._pages:
            p.close()
            p.deleteLater()
        self._pages.clear()
        app = QApplication.instance()
        if app is not None:
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()

    def _make_page(self) -> RepeatIssuesManagementPage:
        page = RepeatIssuesManagementPage(self.mock_main_window, self._host)
        self._pages.append(page)
        return page

    def test_initialization(self) -> None:
        page = self._make_page()
        self.assertEqual("潛在重複異常管理", page.title_label.text())
        self.assertEqual(8, page.table.columnCount())
        self.assertTrue(page.source_case_card.isHidden())
        self.assertFalse(page.confirm_btn.isEnabled())
        self.assertFalse(page.dismiss_btn.isEnabled())

    def test_load_case_with_anomaly_id(self) -> None:
        page = self._make_page()

        def _mock_detail(aid: str) -> dict:
            return self.source_detail if aid == "aid-1" else self.peer_detail

        with mock.patch.object(_anomaly_service, "get_anomaly_detail", side_effect=_mock_detail), \
             mock.patch.object(_anomaly_workbench_service, "get_root_cause", return_value={"statement": "測試根因"}), \
             mock.patch.object(repeat_issue_service, "list_repeat_issues", return_value=self.mock_repeat_rows):
            page.load_case("aid-1")

        self.assertFalse(page.source_case_card.isHidden())
        self.assertIn("20260629001", page.source_case_title.text())
        self.assertEqual(1, page.table.rowCount())
        self.assertEqual("20260323001", page.table.item(0, 1).text())
        self.assertEqual("75", page.table.item(0, 5).text())
        self.assertEqual("待確認", page.table.item(0, 6).text())

        self.assertIn("20260629001", page.sc_header.text())
        self.assertIn("20260323001", page.pc_header.text())
        self.assertIn("爐溫均溫沒有管制", page.sc_problem.text())
        self.assertIn("迴焊爐溫異常偏低", page.pc_problem.text())
        self.assertTrue(page.confirm_btn.isEnabled())
        self.assertTrue(page.dismiss_btn.isEnabled())

    def test_update_disposition_confirmed_and_dismissed(self) -> None:
        page = self._make_page()

        def _mock_detail(aid: str) -> dict:
            return self.source_detail if aid == "aid-1" else self.peer_detail

        with mock.patch.object(_anomaly_service, "get_anomaly_detail", side_effect=_mock_detail), \
             mock.patch.object(_anomaly_workbench_service, "get_root_cause", return_value=None), \
             mock.patch.object(repeat_issue_service, "list_repeat_issues", return_value=self.mock_repeat_rows), \
             mock.patch.object(repeat_issue_service, "set_repeat_link_disposition") as mock_set:
            page.load_case("aid-1")

            page._mark_confirmed()
            mock_set.assert_called_with("aid-1", "aid-2", repeat_issue_service.DISPOSITION_CONFIRMED)
            self.assertEqual("已確認重複", page.table.item(0, 6).text())
            self.assertIn("已確認重複", page.pc_header.text())

            page._mark_dismissed()
            mock_set.assert_called_with("aid-1", "aid-2", repeat_issue_service.DISPOSITION_DISMISSED)
            self.assertEqual("已排除", page.table.item(0, 6).text())
            self.assertIn("已排除", page.pc_header.text())

            page._mark_pending()
            mock_set.assert_called_with("aid-1", "aid-2", repeat_issue_service.DISPOSITION_PENDING)
            self.assertEqual("待確認", page.table.item(0, 6).text())

    def test_navigation_actions(self) -> None:
        page = self._make_page()

        def _mock_detail(aid: str) -> dict:
            return self.source_detail if aid == "aid-1" else self.peer_detail

        with mock.patch.object(_anomaly_service, "get_anomaly_detail", side_effect=_mock_detail), \
             mock.patch.object(_anomaly_workbench_service, "get_root_cause", return_value=None), \
             mock.patch.object(repeat_issue_service, "list_repeat_issues", return_value=self.mock_repeat_rows):
            page.load_case("aid-1")

            page._open_peer_detail()
            self.mock_main_window.open_anomaly_management.assert_called_with("aid-2")

            page._open_source_detail()
            self.mock_main_window.open_anomaly_management.assert_called_with("aid-1")

            page._on_back_clicked()
            self.mock_main_window.open_anomaly_management.assert_called_with("aid-1")


if __name__ == "__main__":
    unittest.main()