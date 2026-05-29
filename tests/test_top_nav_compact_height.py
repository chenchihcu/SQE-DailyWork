from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from ui.main_window import (
    HOME_PAGE_INDEX,
    ANOMALY_PAGE_INDEX,
    VISIT_PAGE_INDEX,
    STATS_PAGE_INDEX,
    CLOSED_PAGE_INDEX,
    MASTER_PAGE_INDEX,
    MainWindow,
)
from ui.sidebar_nav import SidebarNav
from ui.theme import apply_app_theme


_EXPECTED_NAV_LABELS = [
    "首頁",
    "異常管理",
    "訪廠紀錄",
    "統計分析",
    "已結案紀錄",
    "基礎資料",
]


class MainWorkflowTabTests(unittest.TestCase):
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

    def test_sidebar_nav_exists_with_correct_labels(self) -> None:
        sidebar = self.window.sidebar
        self.assertIsInstance(sidebar, SidebarNav)
        self.assertEqual(len(sidebar._buttons), len(_EXPECTED_NAV_LABELS))
        for i, label in enumerate(_EXPECTED_NAV_LABELS):
            btn = sidebar._buttons[i]
            self.assertIsNotNone(btn)

    def test_sidebar_has_six_nav_items(self) -> None:
        self.assertEqual(6, len(self.window.sidebar._buttons))

    def test_legacy_button_nav_is_removed(self) -> None:
        nav_tabs = [
            button
            for button in self.window.findChildren(QPushButton)
            if button.property("role") == "navTab"
        ]
        self.assertEqual([], nav_tabs)
        self.assertFalse(hasattr(self.window, "btn_master"))

    def test_sidebar_visible_at_minimum_window_size(self) -> None:
        self.window.resize(self.window.minimumSize())
        self.app.processEvents()
        sidebar = self.window.sidebar
        self.assertTrue(sidebar.isVisible())
        self.assertGreater(sidebar.width(), 0)

    def test_switch_primary_page_updates_sidebar_active_state(self) -> None:
        self.window._switch_primary_page(ANOMALY_PAGE_INDEX)
        self.app.processEvents()
        self.assertEqual(ANOMALY_PAGE_INDEX, self.window.stack.currentIndex())
        self.assertIs(self.window.stack.currentWidget(), self.window.events_widget)
        active_btn = self.window.sidebar._buttons[ANOMALY_PAGE_INDEX]
        self.assertEqual("true", active_btn.property("nav_active"))


if __name__ == "__main__":
    unittest.main()
