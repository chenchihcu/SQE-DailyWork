from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QHBoxLayout, QTableWidget, QVBoxLayout

from database.product_item_category import MASTER_SEMI_FINISHED_CATEGORIES
from database.supplier_category import SUPPLIER_CATEGORY_RAW_MATERIAL
from ui.widgets.master_data_widget import MasterDataProductPage, MasterDataSupplierPage


class _DummyMainWindow:
    def refresh_all_views(self) -> None:
        return


class MasterDataLayoutOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            pass  # do not terminate shared QApplication singleton in test runner

    def setUp(self) -> None:
        self._list_suppliers_patch = patch(
            "ui.widgets.master_data_widget._supplier_service.list_suppliers",
            return_value=[],
        )
        self._list_products_patch = patch(
            "ui.widgets.master_data_widget._product_service.list_products",
            return_value=[],
        )
        self._list_suppliers_patch.start()
        self._list_products_patch.start()
        self.supplier_widget = MasterDataSupplierPage(
            _DummyMainWindow(),
            SUPPLIER_CATEGORY_RAW_MATERIAL,
            page_label="原物料供應商",
            lazy_load=False,
        )
        self.product_widget = MasterDataProductPage(
            _DummyMainWindow(),
            MASTER_SEMI_FINISHED_CATEGORIES,
            page_label="半成品/成品",
            lazy_load=False,
        )
        self.supplier_widget.show()
        self.product_widget.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.supplier_widget.close()
        self.product_widget.close()
        self.app.processEvents()
        self._list_products_patch.stop()
        self._list_suppliers_patch.stop()

    def test_supplier_page_uses_toolbar_and_table_only_panel(self) -> None:
        content_layout = self.supplier_widget.content_host.layout()
        self.assertIsNotNone(content_layout)
        assert content_layout is not None
        self.assertEqual(1, content_layout.count())
        panel = content_layout.itemAt(0).widget()
        self.assertIsNotNone(panel)
        assert panel is not None
        layout = panel.layout()
        self.assertIsNotNone(layout)
        assert layout is not None
        self.assertEqual(2, layout.count())
        table = layout.itemAt(0).widget()
        self.assertIsInstance(table, QTableWidget)
        self.assertIs(table, self.supplier_widget.supplier_table)

    def test_top_toolbar_contains_single_primary_row_with_left_query(self) -> None:
        toolbar = self.supplier_widget.inline_toolbar
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
        self.assertGreaterEqual(
            primary_layout.indexOf(self.supplier_widget.query_input), 0
        )
        self.assertEqual(220, self.supplier_widget.query_input.minimumWidth())
        self.assertEqual(340, self.supplier_widget.query_input.maximumWidth())

    def test_master_toolbar_no_longer_has_inline_editor_inputs(self) -> None:
        self.assertFalse(hasattr(self.supplier_widget, "editor_stack"))
        self.assertFalse(hasattr(self.supplier_widget, "supplier_name_input"))
        self.assertFalse(hasattr(self.product_widget, "product_code_input"))
        self.assertFalse(hasattr(self.product_widget, "product_name_input"))
        self.assertFalse(hasattr(self.product_widget, "product_supplier_combo"))
        self.assertFalse(hasattr(self.product_widget, "product_stage_combo"))

    def test_compact_button_labels_keep_full_tooltips(self) -> None:
        self.assertEqual("新增", self.supplier_widget.btn_supplier_create.text())
        self.assertEqual("更新", self.supplier_widget.btn_supplier_update.text())
        self.assertEqual("停用", self.supplier_widget.btn_supplier_toggle.text())
        self.assertEqual("刪除", self.supplier_widget.btn_supplier_delete.text())
        self.assertEqual("刪選", self.supplier_widget.btn_supplier_delete_selected.text())
        self.assertEqual("篩選", self.supplier_widget.btn_supplier_filter.text())
        self.assertEqual("清空", self.supplier_widget.btn_supplier_clear.text())
        self.assertEqual("新增", self.product_widget.btn_product_create.text())
        self.assertEqual("更新", self.product_widget.btn_product_update.text())
        self.assertEqual("停用", self.product_widget.btn_product_toggle.text())
        self.assertEqual("刪除", self.product_widget.btn_product_delete.text())
        self.assertEqual("紀錄", self.product_widget.btn_product_stage_logs.text())
        self.assertEqual("匯入", self.product_widget.btn_product_import.text())
        self.assertEqual("篩選", self.product_widget.btn_product_filter.text())
        self.assertEqual("清空", self.product_widget.btn_product_clear.text())

        self.assertEqual("新增供應商", self.supplier_widget.btn_supplier_create.toolTip())
        self.assertEqual(
            "刪除選取供應商",
            self.supplier_widget.btn_supplier_delete_selected.toolTip(),
        )
        self.assertEqual("新增產品", self.product_widget.btn_product_create.toolTip())
        self.assertEqual(
            "查詢產品階段異動紀錄",
            self.product_widget.btn_product_stage_logs.toolTip(),
        )
        self.assertEqual(
            "從 Excel / ERP 匯出檔匯入共用產品與供應商主檔",
            self.product_widget.btn_product_import.toolTip(),
        )

    def test_master_actions_disabled_until_selection_and_status_names_target(self) -> None:
        self.assertFalse(self.supplier_widget.btn_supplier_update.isEnabled())
        self.assertFalse(self.supplier_widget.btn_supplier_toggle.isEnabled())
        self.assertFalse(self.supplier_widget.btn_supplier_delete.isEnabled())
        self.assertFalse(self.supplier_widget.btn_supplier_delete_selected.isEnabled())
        self.assertEqual(
            "未選取原物料供應商",
            self.supplier_widget.selection_status_label.text(),
        )

        self.supplier_widget._supplier_rows = [
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
        self.supplier_widget._render_supplier_table()
        self.supplier_widget.supplier_table.selectRow(0)
        self.app.processEvents()
        self.assertTrue(self.supplier_widget.btn_supplier_update.isEnabled())
        self.assertTrue(self.supplier_widget.btn_supplier_toggle.isEnabled())
        self.assertTrue(self.supplier_widget.btn_supplier_delete.isEnabled())
        self.assertIn("供應商-A", self.supplier_widget.selection_status_label.text())

        self.assertFalse(self.product_widget.btn_product_update.isEnabled())
        self.assertFalse(self.product_widget.btn_product_toggle.isEnabled())
        self.assertFalse(self.product_widget.btn_product_delete.isEnabled())
        self.assertEqual(
            "未選取半成品/成品",
            self.product_widget.selection_status_label.text(),
        )

        self.product_widget._product_rows = [
            {
                "id": "product-1",
                "product_code": "PN-001",
                "product_name": "產品-A",
                "product_stage": "量產",
                "item_category": "半成品",
                "supplier_name": "供應商-A",
                "secondary_supplier_name": "",
                "is_active": 1,
            }
        ]
        self.product_widget._render_product_table()
        self.product_widget.product_table.selectRow(0)
        self.app.processEvents()
        self.assertTrue(self.product_widget.btn_product_update.isEnabled())
        self.assertTrue(self.product_widget.btn_product_toggle.isEnabled())
        self.assertTrue(self.product_widget.btn_product_delete.isEnabled())
        self.assertIn("[PN-001] 產品-A", self.product_widget.selection_status_label.text())


if __name__ == "__main__":
    unittest.main()
