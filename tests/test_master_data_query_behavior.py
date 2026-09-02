from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from database.product_item_category import (
    ITEM_CATEGORY_RAW_MATERIAL,
    MASTER_SEMI_FINISHED_CATEGORIES,
)
from database.supplier_category import SUPPLIER_CATEGORY_RAW_MATERIAL
from ui.widgets.master_data_widget import MasterDataProductPage, MasterDataSupplierPage


class _DummyMainWindow:
    def refresh_all_views(self) -> None:
        return


class MasterDataQueryBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            pass  # do not terminate shared QApplication singleton in test runner

    def setUp(self) -> None:
        self.suppliers = [
            {
                "id": "sup-1",
                "supplier_name": "Alpha Electronics",
                "contact_name": "王大明",
                "phone": "02-1111-1111",
                "is_active": True,
            },
            {
                "id": "sup-2",
                "supplier_name": "Beta Tech",
                "contact_name": "Alice",
                "phone": "03-2222-2222",
                "is_active": False,
            },
            {
                "id": "sup-3",
                "supplier_name": "Gamma Source",
                "contact_name": "Bob",
                "phone": "04-3333-3333",
                "is_active": True,
            },
        ]
        self.products = [
            {
                "id": "prd-1",
                "product_code": "P-100",
                "product_name": "Panel A",
                "product_stage": "量產",
                "item_category": "半成品",
                "supplier_name": "Alpha Electronics",
                "supplier_id": "sup-1",
                "secondary_supplier_name": "Gamma Source",
                "secondary_supplier_id": "sup-3",
                "is_active": True,
            },
            {
                "id": "prd-2",
                "product_code": "B-200",
                "product_name": "Board B",
                "product_stage": "試產",
                "item_category": "成品",
                "supplier_name": "Beta Tech",
                "supplier_id": "sup-2",
                "secondary_supplier_name": "Alpha Electronics",
                "secondary_supplier_id": "sup-1",
                "is_active": False,
            },
        ]
        self._list_suppliers_patch = patch(
            "ui.widgets.master_data_widget._supplier_service.list_suppliers",
            return_value=self.suppliers,
        )
        self._list_products_patch = patch(
            "ui.widgets.master_data_widget._product_service.list_products",
            return_value=self.products,
        )
        self.list_suppliers_mock = self._list_suppliers_patch.start()
        self.list_products_mock = self._list_products_patch.start()
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

    def test_supplier_enter_filters_locally_by_supplier_name(self) -> None:
        initial_supplier_calls = self.list_suppliers_mock.call_count
        initial_product_calls = self.list_products_mock.call_count

        self.supplier_widget.query_input.setText("alpha")
        self.supplier_widget.query_input.returnPressed.emit()
        self.app.processEvents()

        self.assertEqual(1, self.supplier_widget.supplier_table.rowCount())
        self.assertEqual(
            "Alpha Electronics",
            self.supplier_widget.supplier_table.item(0, 0).text(),
        )
        self.assertEqual("王大明", self.supplier_widget.supplier_table.item(0, 2).text())
        self.assertEqual("alpha", self.supplier_widget._supplier_query_keyword)
        self.assertEqual(initial_supplier_calls, self.list_suppliers_mock.call_count)
        self.assertEqual(initial_product_calls, self.list_products_mock.call_count)

    def test_product_enter_filters_by_primary_secondary_and_stage_fields(self) -> None:
        self.product_widget.query_input.setText("gamma")
        self.product_widget.query_input.returnPressed.emit()
        self.app.processEvents()

        self.assertEqual(1, self.product_widget.product_table.rowCount())
        self.assertEqual("P-100", self.product_widget.product_table.item(0, 0).text())
        self.assertEqual("gamma", self.product_widget._product_query_keyword)

        self.product_widget.query_input.setText("B-200")
        self.product_widget.query_input.returnPressed.emit()
        self.app.processEvents()
        self.assertEqual(1, self.product_widget.product_table.rowCount())
        self.assertEqual("B-200", self.product_widget.product_table.item(0, 0).text())

        self.product_widget.query_input.setText("試產")
        self.product_widget.query_input.returnPressed.emit()
        self.app.processEvents()
        self.assertEqual(1, self.product_widget.product_table.rowCount())
        self.assertEqual("B-200", self.product_widget.product_table.item(0, 0).text())

    def test_product_table_headers_include_category_and_secondary_supplier(self) -> None:
        self.assertEqual(7, self.product_widget.product_table.columnCount())
        headers = [
            self.product_widget.product_table.horizontalHeaderItem(i).text()
            for i in range(self.product_widget.product_table.columnCount())
        ]
        self.assertEqual(
            ["料號", "品名", "料號類別", "階段", "主供應商", "次要供應商", "狀態"],
            headers,
        )

    def test_create_product_uses_dialog_payload_with_secondary_supplier(self) -> None:
        payload = {
            "product_code": "NEW-001",
            "product_name": "New Product",
            "product_stage": "試產",
            "item_category": "半成品",
            "supplier_id": "sup-1",
            "secondary_supplier_id": "sup-3",
        }
        with patch(
            "ui.widgets.master_data_widget._product_service.create_product",
            return_value="new-product-id",
        ) as create_mock, patch(
            "ui.widgets.master_data_product_mixin.QMessageBox.information"
        ), patch.object(
            self.product_widget, "_open_product_dialog", return_value=payload
        ) as open_dialog_mock:
            self.product_widget._create_product()

        open_dialog_mock.assert_called_once_with(initial_data=None, is_edit=False)
        create_mock.assert_called_once_with(payload)

    def test_update_product_uses_dialog_payload_with_secondary_supplier(self) -> None:
        payload = {
            "product_code": "P-100",
            "product_name": "Panel A-Updated",
            "product_stage": "試產",
            "item_category": "半成品",
            "supplier_id": "sup-1",
            "secondary_supplier_id": "sup-2",
        }
        with patch(
            "ui.widgets.master_data_widget._product_service.update_product"
        ) as update_mock, patch(
            "ui.widgets.master_data_product_mixin.QMessageBox.information"
        ), patch.object(
            self.product_widget, "_open_product_dialog", return_value=payload
        ):
            self.product_widget._selected_product_id = "prd-1"
            self.product_widget._update_product()

        update_mock.assert_called_once_with("prd-1", payload)

    def test_update_supplier_uses_dialog_payload(self) -> None:
        payload = {
            "supplier_name": "Alpha Electronics (Renamed)",
            "category": "原物料供應商",
            "contact_name": "王大明",
            "phone": "02-1111-1111",
        }
        self.supplier_widget._selected_supplier_id = "sup-1"
        with (
            patch(
                "ui.widgets.master_data_widget._supplier_service.update_supplier"
            ) as update_supplier_mock,
            patch("ui.widgets.master_data_supplier_mixin.QMessageBox.information"),
            patch.object(self.supplier_widget, "_open_supplier_dialog", return_value=payload),
        ):
            self.supplier_widget._update_supplier()

        update_supplier_mock.assert_called_once_with("sup-1", payload)


if __name__ == "__main__":
    unittest.main()
