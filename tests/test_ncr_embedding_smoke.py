"""Smoke tests for the in-process warehouse nonconforming-product embedding."""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ncr.embed import NCR_NAV_LABELS, NCR_PAGE_OFFSET, DefectTrackerPage
from ui.main_window import (
    HOME_PAGE_INDEX,
    NCR_PAGE_INDEX,
    NCR_PAGE_COUNT,
    MainWindow,
)
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
        # 5 SQE DailyWork pages (首頁, 事件管理, 異常事件統計, 不合格品統計分析, 基礎資料) + 1 warehouse nonconforming-product page.
        self.assertEqual(5 + NCR_PAGE_COUNT, self.window.stack.count())
        self.assertEqual(5 + NCR_PAGE_COUNT, len(self.window.sidebar._buttons))
        self.assertIsNotNone(self.window.ncr)

    def test_ncr_widgets_at_expected_indices(self) -> None:
        self.assertIsInstance(self.window.stack.widget(NCR_PAGE_INDEX), DefectTrackerPage)

    def test_can_switch_into_every_ncr_page(self) -> None:
        for idx in range(NCR_PAGE_OFFSET, NCR_PAGE_OFFSET + NCR_PAGE_COUNT):
            self.window._switch_primary_page(idx)
            self.app.processEvents()
            self.assertEqual(idx, self.window.stack.currentIndex())
            self.assertEqual(idx, self.window.sidebar._active_index)

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
        self.assertEqual(NCR_PAGE_INDEX, self.window.stack.currentIndex())
        self.assertEqual(
            self.window.ncr.tracker_page.FORM_TAB_INDEX,
            self.window.ncr.tracker_page.tabs.currentIndex(),
        )

    def test_nav_labels_match_embed_specs(self) -> None:
        host_buttons = self.window.sidebar._buttons
        for offset, label in enumerate(NCR_NAV_LABELS):
            btn = host_buttons[NCR_PAGE_OFFSET + offset]
            self.assertIsNotNone(btn)
            self.assertEqual(btn._label.text(), label)


if __name__ == "__main__":
    unittest.main()
