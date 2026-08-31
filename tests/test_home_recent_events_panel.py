"""Home daily-cockpit tests: supplier-event queue hub and warehouse shortcuts."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget

from ui.sidebar_nav import (
    PAGE_EVENT_OPEN_ACTIONS,
    PAGE_EVENT_OVERDUE,
    PAGE_EVENT_ROOT_CAUSE,
)
from ui.theme import apply_app_theme
from ui.widgets.home_widget import HomeWidget
from ui.widgets.pagination_bar import PaginationBar


class _DummyMainWindow:
    def __init__(self) -> None:
        self.queue_calls: list[str] = []
        self.warehouse_outsource_calls = 0
        self.warehouse_material_calls = 0
        self.warehouse_unclassified_calls = 0

    def refresh_all_views(self) -> None:
        return

    def open_manager_view(self) -> None:
        return

    def open_supplier_event_queue(self, page_key: str) -> None:
        self.queue_calls.append(page_key)

    def open_warehouse_pending_outsource(self) -> None:
        self.warehouse_outsource_calls += 1

    def open_warehouse_pending_material(self) -> None:
        self.warehouse_material_calls += 1

    def open_warehouse_unclassified_pending(self) -> None:
        self.warehouse_unclassified_calls += 1


class HomeCockpitPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        apply_app_theme(cls.app)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            pass

    def setUp(self) -> None:
        self.host = _DummyMainWindow()
        self.widget = HomeWidget(self.host)
        self.widget.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.widget.close()
        self.app.processEvents()

    def test_home_renders_queue_hub_without_backlog_table(self) -> None:
        self.assertIsNone(self.widget.findChild(QTableWidget, "HomeBacklogTable"))
        self.assertIsNotNone(self.widget.findChild(QPushButton, "HomeQueueOverdueLink"))
        self.assertIsNotNone(self.widget.findChild(QPushButton, "HomeQueueRootCauseLink"))
        self.assertIsNotNone(self.widget.findChild(QPushButton, "HomeQueueOpenActionsLink"))
        self.assertIsNone(self.widget.findChild(PaginationBar))

    def test_home_has_no_kpi_cards_or_retired_panels(self) -> None:
        self.assertFalse(hasattr(self.widget, "_backlog_table"))
        self.assertFalse(hasattr(self.widget, "recent_table"))

    @patch("services.supplier_event_queue_service.get_supplier_event_queue_counts")
    def test_queue_hub_buttons_show_counts_and_route(self, mock_counts) -> None:
        mock_counts.return_value = {
            "overdue_anomaly_count": 2,
            "root_cause_pending_count": 5,
            "open_queue_action_count": 3,
        }
        self.widget.refresh_data()
        self.assertIn("2 件", self.widget._queue_buttons[PAGE_EVENT_OVERDUE].text())
        self.assertIn("5 件", self.widget._queue_buttons[PAGE_EVENT_ROOT_CAUSE].text())
        self.assertIn("3 筆", self.widget._queue_buttons[PAGE_EVENT_OPEN_ACTIONS].text())
        self.widget._queue_buttons[PAGE_EVENT_OVERDUE].click()
        self.app.processEvents()
        self.assertEqual([PAGE_EVENT_OVERDUE], self.host.queue_calls)

    def test_warehouse_shortcut_buttons_are_clickable_navigation(self) -> None:
        for button in (
            self.widget._warehouse_outsource_btn,
            self.widget._warehouse_material_btn,
            self.widget._warehouse_unclassified_btn,
        ):
            with self.subTest(button=button.objectName()):
                self.assertEqual(
                    Qt.CursorShape.PointingHandCursor, button.cursor().shape()
                )
                self.assertTrue(button.toolTip())


if __name__ == "__main__":
    unittest.main()
