from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.theme import apply_app_theme
from ui.widgets.defect_list_widget import EventListWidget
from ui.widgets.event_actions import build_event_action_menu


class _DummyMainWindow:
    def refresh_all_views(self) -> None:
        return

    def open_new_anomaly_dialog(self) -> None:
        return

    def open_new_visit_dialog(self) -> None:
        return

    def _open_master_data(self) -> None:
        return


class EventActionMenuConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_app_theme(cls.app)


    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

    def setUp(self) -> None:
        self.row = {
            "event_id": "anomaly-001",
            "event_date": "2026-04-15",
            "event_type": "ANOMALY",
            "ref_no": "20260415001",
            "supplier_name": "供應商-A",
            "product_name": "產品-A",
            "product_stage": "量產",
            "work_order_no": "WO-001",
            "production_qty": 10,
            "content": "異常內容-A",
            "status": "待處理",
            "linked_visit_id": "visit-001",
        }
        self.main_window = _DummyMainWindow()

    def test_event_query_menu_keeps_pending_linked_anomaly_actions(self) -> None:
        with patch(
            "ui.widgets.defect_list_widget.event_service.list_events",
            return_value=[dict(self.row)],
        ):
            widget = EventListWidget(self.main_window, mode="query")
            widget.show()
            self.app.processEvents()
            menu, _action_map = build_event_action_menu(widget, dict(self.row))
            actions = [action.text() for action in menu.actions()]
            widget.close()
            self.app.processEvents()

        self.assertEqual(
            ["預覽內容", "編輯異常", "刪除異常", "結案", "關聯訪廠", "", "傳送精簡報告至 LINE"],
            actions,
        )


if __name__ == "__main__":
    unittest.main()
