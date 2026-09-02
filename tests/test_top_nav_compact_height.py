from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from ui.main_window import (
    EVENT_CREATE_ANOMALY_PAGE_INDEX,
    EVENT_PAGE_INDEX,
    STATS_PAGE_INDEX,
    MASTER_RAW_SUPPLIER_PAGE_INDEX,
    MainWindow,
)
from ui.sidebar_nav import (
    NAV_LABEL_DB_SETTINGS_GROUP,
    NAV_LABEL_MASTER_OUTSOURCE,
    NAV_LABEL_MASTER_PRODUCT_SUBGROUP,
    NAV_LABEL_MASTER_RAW_MATERIAL,
    NAV_LABEL_MASTER_RAW_SUPPLIER,
    NAV_LABEL_MASTER_SEMI_FINISHED,
    NAV_LABEL_MASTER_SUPPLIER_SUBGROUP,
    PAGE_EVENT_QUERY,
    PAGE_MASTER_OUTSOURCE_SUPPLIER,
    PAGE_MASTER_RAW_MATERIAL,
    PAGE_MASTER_RAW_SUPPLIER,
    PAGE_MASTER_SEMI_FINISHED,
    PAGE_NCR_PENDING,
    PAGE_NCR_PENDING_MATERIAL,
    PAGE_NCR_PENDING_OUTSOURCE,
    PAGE_EVENT_CREATE_ANOMALY,
    SidebarNav,
    _NavButtonRow,
    _NavMasterSubGroup,
)
from ui import layout_constants as lc
from ui.theme import apply_app_theme


# Sidebar labels: event scopes are page-local chips rather than nav rows.
_EXPECTED_NAV_LABELS = [
    "新增異常",
    "事件查詢",
    "作業佇列",
    "異常事件統計",
    "建立不合格品",
    "待處理委外加工",
    "待處理原物料",
    "歷史紀錄",
    "不合格品統計分析",
    "供應商總覽",
    NAV_LABEL_MASTER_RAW_SUPPLIER,
    NAV_LABEL_MASTER_OUTSOURCE,
    NAV_LABEL_MASTER_RAW_MATERIAL,
    NAV_LABEL_MASTER_SEMI_FINISHED,
    "顯示設定",
]


class MainWorkflowTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        pass  # style initialized once in tests/__init__.py
        apply_app_theme(cls.app)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            pass  # do not terminate shared QApplication singleton in test runner

    def setUp(self) -> None:
        # Schema-only / empty-supplier DBs would otherwise block on
        # QMessageBox.warning inside _ensure_has_active_suppliers when
        # tests switch to 新增異常.
        self._suppliers = patch(
            "ui.main_window._product_service.has_active_suppliers",
            return_value=True,
        )
        self._suppliers.start()
        self.addCleanup(self._suppliers.stop)
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
            EVENT_PAGE_INDEX: "事件查詢",
            STATS_PAGE_INDEX: "異常事件統計",
            MASTER_RAW_SUPPLIER_PAGE_INDEX: NAV_LABEL_MASTER_RAW_SUPPLIER,
            EVENT_CREATE_ANOMALY_PAGE_INDEX: "新增異常",
        }
        for page_index, expected_title in expected_titles.items():
            self.window._switch_primary_page(page_index)
            self.app.processEvents()
            title_labels = [
                label.text()
                for label in self.window._header_bar.findChildren(QLabel)
            ]
            self.assertIn(expected_title, title_labels)

    def test_sidebar_has_fifteen_nav_items_and_create_routes(self) -> None:
        self.assertEqual(15, len(self.window.sidebar._buttons))
        self.assertIsNone(
            self.window.sidebar.button_for_action(("page", "VISIT_CREATE"))
        )
        self.assertIsNotNone(
            self.window.sidebar.button_for_action(("page", PAGE_EVENT_CREATE_ANOMALY))
        )

    def test_sidebar_compact_density_uses_shared_layout_constants(self) -> None:
        self.assertEqual(38, lc.SIDEBAR_NAV_ITEM_HEIGHT)
        self.assertEqual(10, lc.SIDEBAR_NAV_GROUP_GAP)
        self.assertEqual(4, lc.SIDEBAR_NAV_TOP_SPACING)

    def test_sidebar_uses_domain_group_headers(self) -> None:
        # 側欄以四組領域標題（非按鈕 QLabel）分隔。
        headers = [
            label.text()
            for label in self.window.sidebar.findChildren(QLabel, "SidebarGroupHeader")
        ]
        self.assertEqual(
            ["供應商事件", "倉庫不合格品", NAV_LABEL_DB_SETTINGS_GROUP, "系統"],
            headers,
        )
        # 非緊湊導覽列帶圖示；並排緊湊主檔列省略圖示。
        for button in self.window.sidebar._buttons:
            icon_label = button.findChild(QLabel, "NavIcon")
            self.assertIsNotNone(icon_label)
            if button.property("nav_compact") == "true":
                continue
            self.assertFalse(icon_label.pixmap().isNull())

    def test_sidebar_db_settings_master_rows_are_paired(self) -> None:
        subgroups = self.window.sidebar.findChildren(_NavMasterSubGroup)
        self.assertEqual(2, len(subgroups))
        rows = self.window.sidebar.findChildren(_NavButtonRow)
        self.assertEqual(2, len(rows))
        for page_key in (
            PAGE_MASTER_RAW_SUPPLIER,
            PAGE_MASTER_OUTSOURCE_SUPPLIER,
            PAGE_MASTER_RAW_MATERIAL,
            PAGE_MASTER_SEMI_FINISHED,
        ):
            self.assertIsNotNone(
                self.window.sidebar.button_for_action(("page", page_key))
            )

    def test_sidebar_db_settings_master_subgroup_labels(self) -> None:
        labels = self.window.sidebar.findChildren(QLabel, "SidebarMasterSubGroupLabel")
        self.assertEqual(2, len(labels))
        self.assertEqual(
            [NAV_LABEL_MASTER_SUPPLIER_SUBGROUP, NAV_LABEL_MASTER_PRODUCT_SUBGROUP],
            [label.text() for label in labels],
        )
        self.assertEqual("supplier", labels[0].property("master_subgroup"))
        self.assertEqual("product", labels[1].property("master_subgroup"))

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
        # 底部「快速建立」兩顆按鈕已移除，改用各頁既有入口（事件查詢工具列、建立不合格品側欄列）。
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
        # 事件頁高亮事件查詢列；目前 scope 由頁內 chips 表示。
        active_btn = self.window.sidebar.button_for_action(("page", PAGE_EVENT_QUERY))
        self.assertIsNotNone(active_btn)
        self.assertEqual("true", active_btn.property("nav_active"))

    def test_create_page_updates_sidebar_active_state(self) -> None:
        self.window._switch_primary_page(EVENT_CREATE_ANOMALY_PAGE_INDEX)
        self.app.processEvents()
        active_btn = self.window.sidebar.button_for_action(
            ("page", PAGE_EVENT_CREATE_ANOMALY)
        )
        self.assertIsNotNone(active_btn)
        assert active_btn is not None
        self.assertEqual("true", active_btn.property("nav_active"))


if __name__ == "__main__":
    unittest.main()
