"""Smoke tests for the in-process warehouse nonconforming-product embedding."""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTabWidget

from ncr.embed import NCR_NAV_LABELS, NCR_PAGE_OFFSET
from ncr.ui.defect_form import DefectFormWidget
from ncr.ui.defect_list import DefectListWidget
from ui.main_window import (
    HOME_PAGE_INDEX,
    NCR_ENTRY_PAGE_INDEX,
    NCR_TRACKING_PAGE_INDEX,
    NCR_TRACE_PAGE_INDEX,
    NCR_PAGE_INDEX,
    NCR_PAGE_COUNT,
    MainWindow,
)
from ui.sidebar_nav import PAGE_NCR_CREATE, PAGE_NCR_PENDING, PAGE_NCR_HISTORY
from ui.theme import apply_app_theme


class NcrEmbeddingSmokeTests(unittest.TestCase):
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

    def test_single_window_hosts_all_pages(self) -> None:
        # 5 SQE DailyWork 頁（首頁, 事件管理, 異常事件統計, 不合格品統計分析, 基礎資料）+ 3 倉庫不合格品工作頁。
        self.assertEqual(5 + NCR_PAGE_COUNT, self.window.stack.count())
        # 側欄按鈕 = 8 固定列（首頁 + 4 事件 scope + 異常事件統計 + 不合格品統計分析 + 基礎資料）+ 3 NCR 導覽列。
        self.assertEqual(8 + NCR_PAGE_COUNT, len(self.window.sidebar._buttons))
        self.assertIsNotNone(self.window.ncr)

    def test_ncr_widgets_at_expected_indices(self) -> None:
        create_page = self.window.stack.widget(NCR_ENTRY_PAGE_INDEX)
        pending_page = self.window.stack.widget(NCR_TRACKING_PAGE_INDEX)
        history_page = self.window.stack.widget(NCR_TRACE_PAGE_INDEX)

        self.assertIsNotNone(create_page.findChild(DefectFormWidget))
        pending_widget = pending_page.findChild(DefectListWidget)
        history_widget = history_page.findChild(DefectListWidget)
        self.assertIsNotNone(pending_widget)
        self.assertIsNotNone(history_widget)
        self.assertEqual("tracking", pending_widget.workflow)
        self.assertEqual("trace", history_widget.workflow)
        for page in (create_page, pending_page, history_page):
            self.assertIsNone(page.findChild(QTabWidget, "defectTrackerTabs"))

    def test_can_switch_into_every_ncr_page(self) -> None:
        actions = [
            ("page", PAGE_NCR_CREATE),
            ("page", PAGE_NCR_PENDING),
            ("page", PAGE_NCR_HISTORY),
        ]
        for offset, idx in enumerate(range(NCR_PAGE_OFFSET, NCR_PAGE_OFFSET + NCR_PAGE_COUNT)):
            self.window._switch_primary_page(idx)
            self.app.processEvents()
            self.assertEqual(idx, self.window.stack.currentIndex())
            ncr_btn = self.window.sidebar.button_for_action(actions[offset])
            self.assertIsNotNone(ncr_btn)
            self.assertEqual("true", ncr_btn.property("nav_active"))

    def test_ncr_uses_shared_database(self) -> None:
        rows = self.window.ncr.conn.execute("PRAGMA database_list").fetchall()
        main_db = next((r[2] for r in rows if r[1] == "main"), "")
        self.assertTrue(main_db.replace("\\", "/").endswith("sqe_v2.db"), main_db)

    def test_open_warehouse_nonconforming_tracker_navigates_in_window(self) -> None:
        self.window._switch_primary_page(HOME_PAGE_INDEX)
        result = self.window.open_warehouse_nonconforming_tracker()
        self.app.processEvents()
        self.assertIsNone(result)
        self.assertEqual(NCR_PAGE_INDEX, self.window.stack.currentIndex())

    def test_open_warehouse_nonconforming_create_navigates_to_form(self) -> None:
        self.window._switch_primary_page(HOME_PAGE_INDEX)
        result = self.window.open_warehouse_nonconforming_create()
        self.app.processEvents()
        self.assertIsNone(result)
        self.assertEqual(NCR_ENTRY_PAGE_INDEX, self.window.stack.currentIndex())
        self.assertIs(self.window.stack.currentWidget(), self.window.ncr.create_page)

    def test_nav_labels_match_embed_specs(self) -> None:
        # 側欄已不再以堆疊索引對齊按鈕；以標籤存在性驗證 NCR 導覽列。
        labels = [btn._label.text() for btn in self.window.sidebar._buttons]
        for label in NCR_NAV_LABELS:
            self.assertIn(label, labels)


if __name__ == "__main__":
    unittest.main()
