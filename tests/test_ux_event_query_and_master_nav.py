"""UX：事件管理篩選列、空狀態、基礎清單返回導覽。"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from services import event_service
from ui.main_window import MainWindow
from ui.theme import apply_app_theme


class _MainNavTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_app_theme(cls.app)

    def setUp(self) -> None:
        self.window = MainWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        self.app.processEvents()

    def test_return_from_master_restores_previous_primary_page(self) -> None:
        from ui.main_window import STATS_PAGE_INDEX
        self.window._switch_primary_page(STATS_PAGE_INDEX)
        self.assertEqual(STATS_PAGE_INDEX, self.window.stack.currentIndex())
        self.window._open_master_data()
        self.app.processEvents()
        self.assertIs(self.window.stack.currentWidget(), self.window.master_widget)
        self.window.return_from_master()
        self.app.processEvents()
        self.assertEqual(STATS_PAGE_INDEX, self.window.stack.currentIndex())
        self.assertIs(self.window.stack.currentWidget(), self.window.stats_widget)

    def test_return_from_master_restores_event_management_page(self) -> None:
        self.window._switch_primary_page(1)
        self.assertEqual(1, self.window.stack.currentIndex())
        self.assertIs(self.window.stack.currentWidget(), self.window.events_widget)
        self.window._open_master_data()
        self.app.processEvents()
        self.assertIs(self.window.stack.currentWidget(), self.window.master_widget)
        self.window.return_from_master()
        self.app.processEvents()
        self.assertEqual(1, self.window.stack.currentIndex())
        self.assertIs(self.window.stack.currentWidget(), self.window.events_widget)


class _EventQueryFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_app_theme(cls.app)

    def setUp(self) -> None:
        self.window = MainWindow()
        self.window.show()
        # For testing generic filter UI, use a generic widget without fixed_scope
        from ui.widgets.defect_list_widget import EventListWidget
        self.w = EventListWidget(self.window, mode="query")
        self.app.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        self.app.processEvents()

    def test_empty_state_message_without_filters(self) -> None:
        self.w._clear_implicit_month_filter()
        self.w._filter_event_type = "ALL"
        self.w._filter_status = "ALL"
        self.w._filter_supplier = ""
        self.w._all_rows = []
        self.w._current_page = 1
        self.w._render_current_page()
        self.app.processEvents()
        self.assertFalse(self.w.empty_state.isHidden())
        empty_texts = [label.text() for label in self.w.empty_state.findChildren(QLabel)]
        self.assertTrue(any("目前沒有事件資料" in text for text in empty_texts))

    def test_empty_state_message_with_filters(self) -> None:
        self.w._clear_implicit_month_filter()
        self.w._filter_status = "ALL"
        self.w._filter_supplier = "測試"
        self.w._all_rows = []
        self.w._current_page = 1
        self.w._render_current_page()
        self.app.processEvents()
        self.assertFalse(self.w.empty_state.isHidden())
        empty_texts = [label.text() for label in self.w.empty_state.findChildren(QLabel)]
        self.assertTrue(any("找不到符合條件" in text for text in empty_texts))

    @patch("services.event_service.list_events", return_value=[])
    def test_apply_quick_filters_syncs_widgets(self, _mock) -> None:
        self.w.apply_quick_filters(
            event_type="ANOMALY",
            supplier_keyword="測試",
            status="待處理",
        )
        self.app.processEvents()
        self.assertIsNone(self.w.event_type_combo)
        assert self.w.event_scope_tab_bar is not None
        assert self.w.status_combo is not None
        self.assertEqual(
            event_service.EVENT_SCOPE_ANOMALY_ONLY,
            self.w.event_scope_tab_bar.tabData(self.w.event_scope_tab_bar.currentIndex()),
        )
        self.assertEqual("待處理", self.w.status_combo.currentData())
        self.assertEqual("測試", self.w.supplier_filter_input.text())


if __name__ == "__main__":
    unittest.main()
