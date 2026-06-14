from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QTabWidget, QTableWidget, QVBoxLayout

from ui.widgets.master_data_widget import MasterDataWidget


class _DummyMainWindow:
    def refresh_all_views(self) -> None:
        return

    def return_from_master(self) -> None:
        return


class MasterDataLayoutOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

    def setUp(self) -> None:
        self._list_suppliers_patch = patch(
            "ui.widgets.master_data_widget.event_service.list_suppliers",
            return_value=[],
        )
        self._list_products_patch = patch(
            "ui.widgets.master_data_widget.event_service.list_products",
            return_value=[],
        )
        self._list_suppliers_patch.start()
        self._list_products_patch.start()
        self.widget = MasterDataWidget(_DummyMainWindow())
        self.widget.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.widget.close()
        self.app.processEvents()
        self._list_products_patch.stop()
        self._list_suppliers_patch.stop()

    def _tabs(self) -> QTabWidget:
        tabs = self.widget.findChild(QTabWidget)
        self.assertIsNotNone(tabs)
        assert tabs is not None
        return tabs

    def test_tabs_use_top_toolbar_and_table_only_panels(self) -> None:
        tabs = self._tabs()
        self.assertIsNone(tabs.cornerWidget(Qt.Corner.TopRightCorner))

        tabs_panel = tabs.parentWidget()
        self.assertIsNotNone(tabs_panel)
        assert tabs_panel is not None
        tabs_layout = tabs_panel.layout()
        self.assertEqual(2, tabs_layout.count())
        self.assertIs(self.widget.inline_toolbar, tabs_layout.itemAt(0).widget())
        self.assertIs(tabs, tabs_layout.itemAt(1).widget())

        for idx, expected_table in (
            (0, self.widget.supplier_table),
            (1, self.widget.product_table),
        ):
            panel = tabs.widget(idx)
            self.assertIsNotNone(panel)
            assert panel is not None
            layout = panel.layout()
            self.assertIsNotNone(layout)
            assert layout is not None
            self.assertEqual(2, layout.count())
            table = layout.itemAt(0).widget()
            self.assertIsInstance(table, QTableWidget)
            self.assertIs(table, expected_table)

    def test_top_toolbar_contains_single_primary_row_with_left_query(self) -> None:
        toolbar = self.widget.inline_toolbar
        layout = toolbar.layout()
        self.assertIsInstance(layout, QVBoxLayout)
        assert layout is not None
        self.assertEqual(1, layout.count())

        primary_row = layout.itemAt(0).widget()
        self.assertIsNotNone(primary_row)
        assert primary_row is not None
        self.assertEqual("MasterPrimaryRow", primary_row.objectName())

        primary_layout = primary_row.layout()
        self.assertIsInstance(primary_layout, QHBoxLayout)
        assert primary_layout is not None
        self.assertGreaterEqual(primary_layout.indexOf(self.widget.query_input), 0)
        self.assertGreaterEqual(primary_layout.indexOf(self.widget.action_stack), 0)
        self.assertEqual(2, self.widget.action_stack.count())
        self.assertEqual(220, self.widget.query_input.minimumWidth())
        self.assertEqual(340, self.widget.query_input.maximumWidth())

    def test_master_toolbar_no_longer_has_inline_editor_inputs(self) -> None:
        self.assertFalse(hasattr(self.widget, "editor_stack"))
        self.assertFalse(hasattr(self.widget, "supplier_name_input"))
        self.assertFalse(hasattr(self.widget, "product_code_input"))
        self.assertFalse(hasattr(self.widget, "product_name_input"))
        self.assertFalse(hasattr(self.widget, "product_supplier_combo"))
        self.assertFalse(hasattr(self.widget, "product_stage_combo"))

    def test_tab_switch_syncs_action_stack_and_query_keywords(self) -> None:
        tabs = self._tabs()
        self.widget._supplier_query_keyword = "供應商-A"
        self.widget._product_query_keyword = "P-100"

        tabs.setCurrentIndex(1)
        self.app.processEvents()
        tabs.setCurrentIndex(0)
        self.app.processEvents()
        self.assertEqual(0, self.widget.action_stack.currentIndex())
        self.assertEqual("供應商-A", self.widget.query_input.text())

        tabs.setCurrentIndex(1)
        self.app.processEvents()
        self.assertEqual(1, self.widget.action_stack.currentIndex())
        self.assertEqual("P-100", self.widget.query_input.text())

    def test_compact_button_labels_keep_full_tooltips(self) -> None:
        self.assertEqual("新增", self.widget.btn_supplier_create.text())
        self.assertEqual("更新", self.widget.btn_supplier_update.text())
        self.assertEqual("停用", self.widget.btn_supplier_toggle.text())
        self.assertEqual("刪除", self.widget.btn_supplier_delete.text())
        self.assertEqual("刪選", self.widget.btn_supplier_delete_selected.text())
        self.assertEqual("篩選", self.widget.btn_supplier_filter.text())
        self.assertEqual("清空", self.widget.btn_supplier_clear.text())
        self.assertEqual("新增", self.widget.btn_product_create.text())
        self.assertEqual("更新", self.widget.btn_product_update.text())
        self.assertEqual("停用", self.widget.btn_product_toggle.text())
        self.assertEqual("刪除", self.widget.btn_product_delete.text())
        self.assertEqual("紀錄", self.widget.btn_product_stage_logs.text())
        self.assertEqual("匯入", self.widget.btn_product_import.text())
        self.assertEqual("篩選", self.widget.btn_product_filter.text())
        self.assertEqual("清空", self.widget.btn_product_clear.text())

        self.assertEqual("新增供應商", self.widget.btn_supplier_create.toolTip())
        self.assertEqual("刪除選取供應商", self.widget.btn_supplier_delete_selected.toolTip())
        self.assertEqual("新增產品", self.widget.btn_product_create.toolTip())
        self.assertEqual("查詢產品階段異動紀錄", self.widget.btn_product_stage_logs.toolTip())
        self.assertEqual(
            "從 Excel / ERP 匯出檔匯入共用產品與供應商主檔",
            self.widget.btn_product_import.toolTip(),
        )

    def test_master_actions_disabled_until_selection_and_status_names_target(self) -> None:
        self.assertFalse(self.widget.btn_supplier_update.isEnabled())
        self.assertFalse(self.widget.btn_supplier_toggle.isEnabled())
        self.assertFalse(self.widget.btn_supplier_delete.isEnabled())
        self.assertFalse(self.widget.btn_supplier_delete_selected.isEnabled())
        self.assertEqual("未選取供應商", self.widget.selection_status_label.text())

        self.widget._supplier_rows = [
            {
                "id": "supplier-1",
                "supplier_name": "供應商-A",
                "contact_name": "",
                "department": "",
                "contact_email": "",
                "phone": "",
                "is_active": 1,
            }
        ]
        self.widget._render_supplier_table()
        self.widget.supplier_table.selectRow(0)
        self.app.processEvents()
        self.assertTrue(self.widget.btn_supplier_update.isEnabled())
        self.assertTrue(self.widget.btn_supplier_toggle.isEnabled())
        self.assertTrue(self.widget.btn_supplier_delete.isEnabled())
        self.assertIn("供應商-A", self.widget.selection_status_label.text())

        self.widget.tabs.setCurrentIndex(1)
        self.app.processEvents()
        self.assertFalse(self.widget.btn_product_update.isEnabled())
        self.assertFalse(self.widget.btn_product_toggle.isEnabled())
        self.assertFalse(self.widget.btn_product_delete.isEnabled())
        self.assertEqual("未選取產品", self.widget.selection_status_label.text())

        self.widget._product_rows = [
            {
                "id": "product-1",
                "product_code": "PN-001",
                "product_name": "產品-A",
                "product_stage": "量產",
                "supplier_name": "供應商-A",
                "secondary_supplier_name": "",
                "is_active": 1,
            }
        ]
        self.widget._render_product_table()
        self.widget.product_table.selectRow(0)
        self.app.processEvents()
        self.assertTrue(self.widget.btn_product_update.isEnabled())
        self.assertTrue(self.widget.btn_product_toggle.isEnabled())
        self.assertTrue(self.widget.btn_product_delete.isEnabled())
        self.assertIn("[PN-001] 產品-A", self.widget.selection_status_label.text())


if __name__ == "__main__":
    unittest.main()
