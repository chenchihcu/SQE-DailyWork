from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.widgets.master_data_widget import MasterDataWidget


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
            cls.app.quit()

    def setUp(self) -> None:
        suppliers = [
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
        products = [
            {
                "id": "prd-1",
                "product_code": "P-100",
                "product_name": "Panel A",
                "product_stage": "量產",
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
                "supplier_name": "Beta Tech",
                "supplier_id": "sup-2",
                "secondary_supplier_name": "Alpha Electronics",
                "secondary_supplier_id": "sup-1",
                "is_active": False,
            },
        ]
        self._list_suppliers_patch = patch(
            "ui.widgets.master_data_widget.event_service.list_suppliers",
            return_value=suppliers,
        )
        self._list_products_patch = patch(
            "ui.widgets.master_data_widget.event_service.list_products",
            return_value=products,
        )
        self.list_suppliers_mock = self._list_suppliers_patch.start()
        self.list_products_mock = self._list_products_patch.start()
        self.widget = MasterDataWidget(_DummyMainWindow())
        self.widget.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.widget.close()
        self.app.processEvents()
        self._list_products_patch.stop()
        self._list_suppliers_patch.stop()

    def test_supplier_enter_filters_locally_by_supplier_name(self) -> None:
        initial_supplier_calls = self.list_suppliers_mock.call_count
        initial_product_calls = self.list_products_mock.call_count

        self.widget.tabs.setCurrentIndex(0)
        self.app.processEvents()
        self.widget.query_input.setText("alpha")
        self.widget.query_input.returnPressed.emit()
        self.app.processEvents()

        self.assertEqual(1, self.widget.supplier_table.rowCount())
        self.assertEqual("Alpha Electronics", self.widget.supplier_table.item(0, 0).text())
        self.assertEqual("王大明", self.widget.supplier_table.item(0, 1).text())
        self.assertEqual("alpha", self.widget._supplier_query_keyword)
        self.assertEqual(initial_supplier_calls, self.list_suppliers_mock.call_count)
        self.assertEqual(initial_product_calls, self.list_products_mock.call_count)

    def test_product_enter_filters_by_primary_secondary_and_stage_fields(self) -> None:
        self.widget.tabs.setCurrentIndex(1)
        self.app.processEvents()
        self.widget.query_input.setText("gamma")
        self.widget.query_input.returnPressed.emit()
        self.app.processEvents()

        self.assertEqual(1, self.widget.product_table.rowCount())
        self.assertEqual("P-100", self.widget.product_table.item(0, 0).text())
        self.assertEqual("Gamma Source", self.widget.product_table.item(0, 4).text())
        self.assertEqual("gamma", self.widget._product_query_keyword)

        self.widget.query_input.setText("B-200")
        self.widget.query_input.returnPressed.emit()
        self.app.processEvents()
        self.assertEqual(1, self.widget.product_table.rowCount())
        self.assertEqual("B-200", self.widget.product_table.item(0, 0).text())

        self.widget.query_input.setText("試產")
        self.widget.query_input.returnPressed.emit()
        self.app.processEvents()
        self.assertEqual(1, self.widget.product_table.rowCount())
        self.assertEqual("B-200", self.widget.product_table.item(0, 0).text())
        self.assertEqual("試產", self.widget.product_table.item(0, 2).text())

    def test_product_table_headers_include_secondary_supplier_column(self) -> None:
        self.widget.tabs.setCurrentIndex(1)
        self.app.processEvents()
        self.assertEqual(6, self.widget.product_table.columnCount())
        headers = [
            self.widget.product_table.horizontalHeaderItem(i).text()
            for i in range(self.widget.product_table.columnCount())
        ]
        self.assertEqual(
            ["料號", "品名", "階段", "主供應商", "次要供應商", "狀態"],
            headers,
        )

    def test_create_product_uses_dialog_payload_with_secondary_supplier(self) -> None:
        payload = {
            "product_code": "NEW-001",
            "product_name": "New Product",
            "product_stage": "試產",
            "supplier_id": "sup-1",
            "secondary_supplier_id": "sup-3",
        }
        with patch(
            "ui.widgets.master_data_widget.event_service.create_product",
            return_value="new-product-id",
        ) as create_mock, patch(
            "ui.widgets.master_data_widget.QMessageBox.information"
        ), patch.object(
            self.widget, "_open_product_dialog", return_value=payload
        ) as open_dialog_mock:
            self.widget.tabs.setCurrentIndex(1)
            self.app.processEvents()
            self.widget._create_product()

        open_dialog_mock.assert_called_once_with(initial_data=None, is_edit=False)
        create_mock.assert_called_once_with(payload)

    def test_update_product_uses_dialog_payload_with_secondary_supplier(self) -> None:
        payload = {
            "product_code": "P-100",
            "product_name": "Panel A-Updated",
            "product_stage": "試產",
            "supplier_id": "sup-1",
            "secondary_supplier_id": "sup-2",
        }
        with patch(
            "ui.widgets.master_data_widget.event_service.update_product"
        ) as update_mock, patch(
            "ui.widgets.master_data_widget.QMessageBox.information"
        ), patch.object(
            self.widget, "_open_product_dialog", return_value=payload
        ):
            self.widget.tabs.setCurrentIndex(1)
            self.app.processEvents()
            self.widget._selected_product_id = "prd-1"
            self.widget._update_product()

        update_mock.assert_called_once_with("prd-1", payload)

    def test_tab_switch_keeps_independent_query_keywords(self) -> None:
        self.widget.tabs.setCurrentIndex(0)
        self.app.processEvents()
        self.widget.query_input.setText("alpha")
        self.widget.query_input.returnPressed.emit()
        self.app.processEvents()
        self.assertEqual("alpha", self.widget._supplier_query_keyword)

        self.widget.tabs.setCurrentIndex(1)
        self.app.processEvents()
        self.assertEqual("", self.widget.query_input.text())
        self.widget.query_input.setText("beta")
        self.widget.query_input.returnPressed.emit()
        self.app.processEvents()
        self.assertEqual("beta", self.widget._product_query_keyword)

        self.widget.tabs.setCurrentIndex(0)
        self.app.processEvents()
        self.assertEqual("alpha", self.widget.query_input.text())

        self.widget.tabs.setCurrentIndex(1)
        self.app.processEvents()
        self.assertEqual("beta", self.widget.query_input.text())

    def test_update_supplier_uses_dialog_payload(self) -> None:
        payload = {
            "supplier_name": "Alpha Electronics (Renamed)",
            "contact_name": "王大明",
            "phone": "02-1111-1111",
        }
        self.widget._selected_supplier_id = "sup-1"
        with (
            patch(
                "ui.widgets.master_data_widget.event_service.update_supplier"
            ) as update_supplier_mock,
            patch("ui.widgets.master_data_widget.QMessageBox.information"),
            patch.object(self.widget, "_open_supplier_dialog", return_value=payload),
        ):
            self.widget._update_supplier()

        update_supplier_mock.assert_called_once_with("sup-1", payload)


if __name__ == "__main__":
    unittest.main()
