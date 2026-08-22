from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialogButtonBox, QFrame, QPushButton, QScrollArea

from ui.main_window import (
    EVENT_CREATE_ANOMALY_PAGE_INDEX,
    EVENT_CREATE_VISIT_PAGE_INDEX,
    MainWindow,
)
from ui.widgets.home_widget import HomeWidget


class _HomeHost:
    def __init__(self) -> None:
        self.visit_calls = 0
        self.defect_calls = 0
        self.anomaly_calls = 0

    def refresh_all_views(self) -> None:
        return

    def open_new_visit_dialog(self) -> None:
        self.visit_calls += 1

    def open_new_visit_defect_dialog(self) -> None:
        self.defect_calls += 1

    def open_new_anomaly_dialog(self) -> None:
        self.anomaly_calls += 1

    def open_warehouse_nonconforming_tracker(self) -> None:
        return


class LightweightVisitEntryRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            pass  # do not terminate shared QApplication singleton in test runner

    def test_home_no_longer_owns_lightweight_visit_defect_button(self) -> None:
        host = _HomeHost()
        widget = HomeWidget(host)
        self.addCleanup(widget.close)

        button_texts = [
            button.text().strip()
            for button in widget.findChildren(QPushButton)
            if button.text().strip()
        ]

        self.assertNotIn("登錄訪廠缺失", button_texts)
        self.assertEqual(0, host.defect_calls)
        self.assertEqual(0, host.anomaly_calls)

    def test_main_window_routes_formal_anomaly_entry_to_full_page(self) -> None:
        with patch("ui.main_window._product_service.has_active_suppliers", return_value=True):
            window = MainWindow()
            self.addCleanup(window.close)
            window.open_new_anomaly_dialog()

        self.assertEqual(EVENT_CREATE_ANOMALY_PAGE_INDEX, window.stack.currentIndex())
        self.assertIs(window.new_anomaly_page, window.stack.currentWidget())
        self.assertTrue(window.new_anomaly_page.success_panel.isHidden())

    def test_main_window_routes_visit_entry_to_full_page(self) -> None:
        with patch("ui.main_window._product_service.has_active_suppliers", return_value=True):
            window = MainWindow()
            self.addCleanup(window.close)
            window.open_new_visit_dialog()

        self.assertEqual(EVENT_CREATE_VISIT_PAGE_INDEX, window.stack.currentIndex())
        self.assertIs(window.new_visit_page, window.stack.currentWidget())

    def test_full_page_visit_entry_scrolls_content_but_keeps_actions_fixed(self) -> None:
        """A full-page create route has one scroll owner and one command row."""
        window = MainWindow()
        self.addCleanup(window.close)
        page = window.new_visit_page
        form = page.form

        self.assertIsInstance(page.workflow_shell.content_scroll, QScrollArea)
        self.assertEqual("CreateWorkflowScroll", page.workflow_shell.content_scroll.objectName())
        self.assertIs(page.workflow_shell.content_scroll.widget(), form)
        self.assertIsNone(form.form_scroll)
        self.assertIsNone(form._button_box)
        self.assertEqual([], form.findChildren(QDialogButtonBox))
        self.assertEqual("返回清單", page.return_button.text())
        self.assertEqual("儲存", page.save_button.text())
        self.assertTrue(page.success_panel.isHidden())
        self.assertFalse(page.save_button.isEnabled())
        basic_card = form.findChild(QFrame, "VisitBasicInfoCard")
        summary_card = form.findChild(QFrame, "VisitSummaryCard")
        self.assertIsNotNone(basic_card)
        self.assertIsNotNone(summary_card)

    def test_full_page_anomaly_entry_uses_the_same_single_scroll_contract(self) -> None:
        window = MainWindow()
        self.addCleanup(window.close)
        page = window.new_anomaly_page
        form = page.form

        self.assertIs(page.workflow_shell.content_scroll.widget(), form)
        self.assertIsNone(form.form_scroll)
        self.assertIsNone(form._button_box)
        self.assertEqual([], form.findChildren(QDialogButtonBox))
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

    def test_main_window_legacy_defect_entry_routes_to_full_visit_page(self) -> None:
        with patch("ui.main_window._product_service.has_active_suppliers", return_value=True):
            window = MainWindow()
            self.addCleanup(window.close)
            window.open_new_visit_defect_dialog()

        self.assertEqual(EVENT_CREATE_VISIT_PAGE_INDEX, window.stack.currentIndex())
        self.assertIs(window.new_visit_page, window.stack.currentWidget())

    def test_visit_page_can_submit_requires_supplier_and_product(self) -> None:
        with patch("ui.main_window._product_service.has_active_suppliers", return_value=True):
            window = MainWindow()
            self.addCleanup(window.close)
            form = window.new_visit_page.form
            self.assertFalse(form.can_submit())

            products = [
                {
                    "id": "prd-1",
                    "product_code": "P-001",
                    "product_name": "產品一號",
                    "product_stage": "試產",
                }
            ]
            with patch(
                "services.event_service.list_active_products_for_supplier",
                return_value=products,
            ):
                form.supplier_combo.addItem("供應商A", "sup-1")
                form.supplier_combo.setCurrentIndex(form.supplier_combo.findData("sup-1"))
                self.app.processEvents()
                self.assertFalse(form.can_submit())
                product_idx = form.product_combo.findData("prd-1")
                self.assertGreaterEqual(product_idx, 0)
                form.product_combo.setCurrentIndex(product_idx)
                self.app.processEvents()
                self.assertTrue(form.can_submit())


if __name__ == "__main__":
    unittest.main()
