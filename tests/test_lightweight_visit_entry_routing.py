from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialogButtonBox, QScrollArea

from ui.main_window import EVENT_CREATE_ANOMALY_PAGE_INDEX, MainWindow
from ui.sidebar_nav import PAGE_ANOMALY_CREATE, PAGE_EVENT_CREATE_VISIT, PAGE_VISIT_CREATE
from ui.widgets.event_create_page import EventCreatePage


class LightweightVisitEntryRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            pass  # do not terminate shared QApplication singleton in test runner

    def test_main_window_routes_formal_anomaly_entry_to_full_page(self) -> None:
        with patch("ui.main_window._product_service.has_active_suppliers", return_value=True):
            window = MainWindow()
            self.addCleanup(window.close)
            window.open_new_anomaly_dialog()

        self.assertEqual(EVENT_CREATE_ANOMALY_PAGE_INDEX, window.stack.currentIndex())
        self.assertIs(window.new_anomaly_page, window.stack.currentWidget())
        self.assertTrue(window.new_anomaly_page.success_panel.isHidden())

    def test_visit_create_entrypoints_are_removed(self) -> None:
        with patch("ui.main_window._product_service.has_active_suppliers", return_value=True):
            window = MainWindow()
            self.addCleanup(window.close)

        self.assertFalse(hasattr(window, "new_visit_page"))
        self.assertFalse(hasattr(window, "open_new_visit_dialog"))
        self.assertFalse(hasattr(window, "open_new_visit_create_page"))
        self.assertFalse(hasattr(window, "open_new_visit_defect_dialog"))
        self.assertIsNone(window.sidebar.button_for_action(("page", PAGE_VISIT_CREATE)))
        self.assertIsNone(window.sidebar.button_for_action(("page", PAGE_EVENT_CREATE_VISIT)))
        self.assertIsNotNone(window.sidebar.button_for_action(("page", PAGE_ANOMALY_CREATE)))
        with self.assertRaises(ValueError):
            EventCreatePage(window, "visit")
        self.assertFalse(hasattr(MainWindow, "open_new_visit_create_page"))
        self.assertFalse(hasattr(MainWindow, "open_new_visit_dialog"))
        self.assertFalse(hasattr(MainWindow, "open_new_visit_defect_dialog"))

    def test_full_page_anomaly_entry_uses_the_same_single_scroll_contract(self) -> None:
        window = MainWindow()
        self.addCleanup(window.close)
        page = window.new_anomaly_page
        form = page.form

        self.assertIsInstance(page.workflow_shell.content_scroll, QScrollArea)
        self.assertEqual("CreateWorkflowScroll", page.workflow_shell.content_scroll.objectName())
        self.assertIs(page.workflow_shell.content_scroll.widget(), form)
        self.assertIsNone(form.form_scroll)
        self.assertIsNone(form._button_box)
        self.assertEqual([], form.findChildren(QDialogButtonBox))
        self.assertEqual("返回清單", page.return_button.text())
        self.assertEqual("儲存", page.save_button.text())
        self.assertFalse(page.save_button.isEnabled())

    def test_create_page_success_offers_list_or_continue_actions(self) -> None:
        window = MainWindow()
        self.addCleanup(window.close)
        page = window.new_anomaly_page
        page._on_form_saved("已建立異常單：20260813001")

        self.assertFalse(page.success_panel.isHidden())
        self.assertIn("已建立異常單", page.success_message.text())
        self.assertEqual("查看清單", page.view_list_button.text())
        self.assertEqual("繼續新增", page.continue_button.text())
        old_form = page.form
        page.reset_form()
        self.assertIsNot(old_form, page.form)
        self.assertFalse(page.success_panel.isVisible())


if __name__ == "__main__":
    unittest.main()
