"""Tests for event Quick Review panel and next-action resolver."""

from __future__ import annotations

import os
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication

from ui.theme import apply_app_theme
from ui.widgets.defect_list_widget import EventListWidget
from ui.widgets.event_next_action import (
    HANDLER_ADD_ACTION,
    HANDLER_CLOSE,
    HANDLER_HANDLE_OVERDUE,
    HANDLER_OPEN_FULL,
    HANDLER_ROOT_CAUSE,
    HANDLER_VERIFY,
    resolve_next_action,
)
from ui.widgets.event_quick_review_panel import EventQuickReviewPanel, format_due_countdown


class _DummyMainWindow:
    def refresh_all_views(self) -> None:
        return

    def open_anomaly_management(self, anomaly_id: str, *, edit: bool = False) -> None:
        return


class EventQuickReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        apply_app_theme(cls.app)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            pass

    def _drain_events(self) -> None:
        self.app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def _sample_row(self) -> dict:
        return {
            "event_id": "anomaly-1",
            "ref_no": "20260908001",
            "event_type": "ANOMALY",
            "supplier_name": "欣興電子",
            "product_code": "ABC-12345",
            "product_stage": "SMT",
            "category": "錫橋短路",
            "content": "錫橋",
            "status": "待處理",
            "overdue": True,
            "current_action": {
                "id": "action-1",
                "description": "完成 D3 暫時對策",
                "due_date": "2099-12-31 18:00:00",
            },
            "open_action_count": 1,
            "root_cause_status": "尚未開始",
            "corrective_action_status": "—",
            "verification_result": "—",
            "attachment_count": 0,
        }

    def test_resolve_next_action_rules(self) -> None:
        overview = {"overdue": True}
        detail = {"status": "待處理"}
        self.assertEqual(
            HANDLER_HANDLE_OVERDUE,
            resolve_next_action(overview, detail).handler_key,
        )

        overview = {"overdue": False, "open_action_count": 0, "current_action": None}
        self.assertEqual(
            HANDLER_ADD_ACTION,
            resolve_next_action(overview, detail).handler_key,
        )

        overview = {
            "overdue": False,
            "open_action_count": 1,
            "current_action": {"description": "x"},
            "root_cause_status": "調查中",
        }
        self.assertEqual(
            HANDLER_ROOT_CAUSE,
            resolve_next_action(overview, detail).handler_key,
        )

        overview = {
            "overdue": False,
            "open_action_count": 1,
            "current_action": {"description": "x"},
            "root_cause_status": "已驗證",
            "corrective_action_status": "已完成",
            "verification_result": "待驗證",
        }
        self.assertEqual(
            HANDLER_VERIFY,
            resolve_next_action(overview, detail).handler_key,
        )

        overview = {
            "overdue": False,
            "open_action_count": 1,
            "current_action": {"description": "x"},
            "root_cause_status": "已驗證",
            "corrective_action_status": "已完成",
            "verification_result": "通過",
        }
        self.assertEqual(
            HANDLER_CLOSE,
            resolve_next_action(overview, detail).handler_key,
        )

        self.assertEqual(
            HANDLER_OPEN_FULL,
            resolve_next_action({}, {"status": "已結案"}).handler_key,
        )

    def test_format_due_countdown_remaining(self) -> None:
        text = format_due_countdown(
            "2099-12-31 18:00:00",
            now=datetime(2099, 12, 31, 16, 0, 0),
        )
        self.assertIn("剩餘", text)
        self.assertIn("2 小時", text)

    def test_panel_empty_state(self) -> None:
        panel = EventQuickReviewPanel()
        panel.show()
        panel.clear()
        self._drain_events()
        self.assertTrue(panel._empty_state.isVisible())
        self.assertFalse(panel._content_scroll.isVisible())

    @patch("ui.widgets.event_quick_review_panel._anomaly_workbench_service.get_overview_card")
    @patch("ui.widgets.event_quick_review_panel._anomaly_service.get_anomaly_detail")
    def test_panel_load_from_row(self, mock_detail, mock_overview) -> None:
        row = self._sample_row()
        mock_detail.return_value = {
            "anomaly_no": row["ref_no"],
            "supplier_name": row["supplier_name"],
            "status": row["status"],
            "pending_items": row["content"],
        }
        mock_overview.return_value = {
            "overdue": True,
            "current_action": row["current_action"],
            "open_action_count": 1,
            "root_cause_status": "尚未開始",
            "corrective_action_status": "—",
            "verification_result": "—",
            "attachment_count": 0,
        }
        panel = EventQuickReviewPanel()
        panel.resize(420, 720)
        panel.show()
        panel.load_from_row(row)
        self._drain_events()
        self.assertIn("20260908001", panel._ref_label.text())
        self.assertTrue(panel.primary_button.isVisible())
        self.assertEqual("處理逾期處置", panel.primary_button.text())

    def test_event_list_selection_updates_quick_review(self) -> None:
        row = self._sample_row()
        with patch(
            "ui.widgets.defect_list_widget._query_service.list_events",
            return_value=[row],
        ), patch(
            "ui.widgets.event_quick_review_panel._anomaly_service.get_anomaly_detail",
            return_value={"status": "待處理", "problem_desc": "錫橋"},
        ), patch(
            "ui.widgets.event_quick_review_panel._anomaly_workbench_service.get_overview_card",
            return_value={
                "overdue": True,
                "current_action": row["current_action"],
                "open_action_count": 1,
                "root_cause_status": "尚未開始",
                "corrective_action_status": "—",
                "verification_result": "—",
                "attachment_count": 0,
            },
        ):
            widget = EventListWidget(_DummyMainWindow(), mode="query")
            widget.resize(1400, 720)
            widget.show()
            self._drain_events()
            self.assertIsNotNone(widget.quick_review_panel)
            widget.table.selectRow(0)
            self._drain_events()
            self.assertIn("20260908001", widget.quick_review_panel._ref_label.text())

    def test_event_list_double_click_opens_details(self) -> None:
        row = self._sample_row()
        main_window = _DummyMainWindow()
        main_window.open_anomaly_management = MagicMock()
        with patch(
            "ui.widgets.defect_list_widget._query_service.list_events",
            return_value=[row],
        ):
            widget = EventListWidget(main_window, mode="query")
            widget.resize(1400, 720)
            widget.show()
            self._drain_events()
            widget._on_table_row_double_clicked(0, 0)
            main_window.open_anomaly_management.assert_called_once_with(
                "anomaly-1",
                edit=False,
            )

    def test_page_change_clears_quick_review_preview(self) -> None:
        rows = [self._sample_row(), dict(self._sample_row(), event_id="anomaly-2", ref_no="20260908002")]
        with patch(
            "ui.widgets.defect_list_widget._query_service.list_events",
            return_value=rows,
        ), patch(
            "ui.widgets.event_quick_review_panel._anomaly_service.get_anomaly_detail",
            return_value={"status": "待處理"},
        ), patch(
            "ui.widgets.event_quick_review_panel._anomaly_workbench_service.get_overview_card",
            return_value={
                "overdue": True,
                "current_action": self._sample_row()["current_action"],
                "open_action_count": 1,
                "root_cause_status": "尚未開始",
                "corrective_action_status": "—",
                "verification_result": "—",
                "attachment_count": 0,
            },
        ):
            widget = EventListWidget(_DummyMainWindow(), mode="query")
            widget._page_size = 1
            widget.resize(1400, 720)
            widget.show()
            widget.refresh_data()
            self._drain_events()
            widget.table.selectRow(0)
            self._drain_events()
            self.assertIn("20260908001", widget.quick_review_panel._ref_label.text())
            widget.pagination.next_btn.click()
            self._drain_events()
            self.assertTrue(widget.quick_review_panel._empty_state.isVisible())

    def test_event_list_collapses_preview_below_breakpoint(self) -> None:
        row = self._sample_row()
        with patch(
            "ui.widgets.defect_list_widget._query_service.list_events",
            return_value=[row],
        ):
            widget = EventListWidget(_DummyMainWindow(), mode="query")
            widget.resize(1100, 720)
            widget.show()
            self._drain_events()
            self.assertFalse(widget.quick_review_panel.isVisible())
            widget.resize(1400, 720)
            self._drain_events()
            self.assertTrue(widget.quick_review_panel.isVisible())


if __name__ == "__main__":
    unittest.main()
