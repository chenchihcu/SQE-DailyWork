from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

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


# Six SQE DailyWork pages followed by the warehouse nonconforming-product page.
_EXPECTED_HOST_NAV_LABELS = [
    "首頁",
    "異常一覽表",
    "訪廠紀錄一覽表",
    "異常事件統計",
    "異常已結案查詢",
    "基礎資料",
]
_EXPECTED_NCR_NAV_LABELS = [
    "不合格品追蹤",
]
_EXPECTED_NAV_LABELS = _EXPECTED_HOST_NAV_LABELS + _EXPECTED_NCR_NAV_LABELS


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
            label_widget = btn.findChild(QLabel, "NavLabel")
            self.assertIsNotNone(label_widget)
            assert label_widget is not None
            self.assertEqual(label, label_widget.text())

    def test_switching_pages_updates_header_titles_with_new_labels(self) -> None:
        expected_titles = {
            ANOMALY_PAGE_INDEX: "異常一覽表",
            VISIT_PAGE_INDEX: "訪廠紀錄一覽表",
            STATS_PAGE_INDEX: "異常事件統計",
            CLOSED_PAGE_INDEX: "異常已結案查詢",
            MASTER_PAGE_INDEX: "基礎資料",
        }
        for page_index, expected_title in expected_titles.items():
            self.window._switch_primary_page(page_index)
            self.app.processEvents()
            title_labels = [
                label.text()
                for label in self.window._header_bar.findChildren(QLabel)
            ]
            self.assertIn(expected_title, title_labels)

    def test_sidebar_has_seven_nav_items(self) -> None:
        # 6 SQE DailyWork pages + 1 embedded warehouse nonconforming-product page = 7.
        self.assertEqual(7, len(self.window.sidebar._buttons))

    def test_sidebar_groups_use_icons_not_text_labels(self) -> None:
        # 分組改以「圖示 + 間距」呈現工作流程結構，不再使用分組標題文字或分隔線。
        self.assertEqual(
            [], self.window.sidebar.findChildren(QLabel, "SidebarGroupLabelText")
        )
        self.assertIsNone(self.window.sidebar.findChild(QLabel, "SidebarGroupLabel"))
        # 每個導覽項目都帶有一個非空白的圖示，作為視覺辨識。
        for button in self.window.sidebar._buttons:
            icon_label = button.findChild(QLabel, "NavIcon")
            self.assertIsNotNone(icon_label)
            self.assertFalse(icon_label.pixmap().isNull())

    def test_sidebar_warehouse_badge_is_available(self) -> None:
        warehouse_button = self.window.sidebar._buttons[-1]
        self.window.sidebar.set_badge(6, 12)
        self.app.processEvents()
        badges = warehouse_button.findChildren(QLabel, "NavBadge")
        self.assertEqual(1, len(badges))
        self.assertEqual("12", badges[0].text())
        self.assertTrue(badges[0].isVisible())

    def test_sidebar_footer_actions_have_distinct_roles(self) -> None:
        self.assertIsNotNone(self.window.sidebar.findChild(QPushButton, "SidebarQuickCreate"))
        self.assertIsNotNone(self.window.sidebar.findChild(QPushButton, "SidebarWarehouseQuickCreate"))
        footer_labels = [
            label.text()
            for label in self.window.sidebar.findChildren(QLabel, "SidebarFooterLabel")
        ]
        self.assertEqual(["快速建立"], footer_labels)

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
