from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from ui.main_window import (
    EVENT_PAGE_INDEX,
    STATS_PAGE_INDEX,
    MASTER_PAGE_INDEX,
    MainWindow,
)
from ui.sidebar_nav import PAGE_NCR_PENDING, SidebarNav
from ui.sidebar_nav import PAGE_NCR_PENDING_MATERIAL, PAGE_NCR_PENDING_OUTSOURCE
from ui.theme import apply_app_theme


# Twelve sidebar nav labels（事件 4 scope + 倉庫 4 workflow pages 升級為一等導覽列）：
# 首頁 + 單獨異常/訪廠發現異常/訪廠紀錄/已結案 + 異常事件統計 + 建立/雙待處理/歷史 + 不合格品統計分析 + 基礎資料。
_EXPECTED_NAV_LABELS = [
    "首頁",
    "單獨異常",
    "訪廠發現異常",
    "訪廠紀錄",
    "已結案",
    "異常事件統計",
    "建立不合格品",
    "待處理委外加工",
    "待處理原物料",
    "歷史紀錄",
    "不合格品統計分析",
    "基礎資料",
]


class MainWorkflowTabTests(unittest.TestCase):
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
            EVENT_PAGE_INDEX: "事件管理",
            STATS_PAGE_INDEX: "異常事件統計",
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

    def test_sidebar_has_twelve_nav_items(self) -> None:
        # 12 nav 按鈕：首頁 + 4 事件 scope + 異常事件統計 + 4 倉庫工作頁 + 不合格品統計分析 + 基礎資料。
        self.assertEqual(12, len(self.window.sidebar._buttons))

    def test_sidebar_uses_domain_group_headers(self) -> None:
        # 側欄以三組領域標題（非按鈕 QLabel）分隔：供應商事件 / 倉庫不合格品 / 系統。
        headers = [
            label.text()
            for label in self.window.sidebar.findChildren(QLabel, "SidebarGroupHeader")
        ]
        self.assertEqual(["供應商事件", "倉庫不合格品", "系統"], headers)
        # 每個導覽項目都帶有一個非空白的圖示，作為視覺辨識。
        for button in self.window.sidebar._buttons:
            icon_label = button.findChild(QLabel, "NavIcon")
            self.assertIsNotNone(icon_label)
            self.assertFalse(icon_label.pixmap().isNull())

    def test_sidebar_warehouse_badge_is_available(self) -> None:
        for action, count in (
            (("page", PAGE_NCR_PENDING_OUTSOURCE), 12),
            (("page", PAGE_NCR_PENDING_MATERIAL), 3),
        ):
            with self.subTest(action=action):
                warehouse_button = self.window.sidebar.button_for_action(action)
                self.assertIsNotNone(warehouse_button)
                assert warehouse_button is not None
                self.window.sidebar.set_badge(action, count)
                self.app.processEvents()
                badges = warehouse_button.findChildren(QLabel, "NavBadge")
                self.assertEqual(1, len(badges))
                self.assertEqual(str(count), badges[0].text())
                self.assertTrue(badges[0].isVisible())
        self.assertEqual(PAGE_NCR_PENDING, PAGE_NCR_PENDING_OUTSOURCE)

    def test_sidebar_footer_quick_create_removed(self) -> None:
        # 底部「快速建立」兩顆按鈕已移除，改用各頁既有入口（事件管理工具列、建立不合格品側欄列）。
        self.assertIsNone(self.window.sidebar.findChild(QPushButton, "SidebarQuickCreate"))
        self.assertIsNone(self.window.sidebar.findChild(QPushButton, "SidebarWarehouseQuickCreate"))
        self.assertEqual(
            [], self.window.sidebar.findChildren(QLabel, "SidebarFooterLabel")
        )

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
        self.window._switch_primary_page(EVENT_PAGE_INDEX)
        self.app.processEvents()
        self.assertEqual(EVENT_PAGE_INDEX, self.window.stack.currentIndex())
        self.assertIs(self.window.stack.currentWidget(), self.window.events_widget)
        # 事件頁高亮的是「目前 scope」對應的側欄列（預設 = 單獨異常）。
        scope = self.window.events_widget._filter_event_scope
        active_btn = self.window.sidebar.button_for_action(("scope", scope))
        self.assertIsNotNone(active_btn)
        self.assertEqual("true", active_btn.property("nav_active"))


if __name__ == "__main__":
    unittest.main()
