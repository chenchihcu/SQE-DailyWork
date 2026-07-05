from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from ui.widgets.master_data_widget import MasterDataWidget


class _DummyMainWindow:
    def refresh_all_views(self) -> None:
        return


class MasterDataSafetyConfirmationsTests(unittest.TestCase):
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
        ]
        products = [
            {
                "id": "prd-1",
                "product_code": "P-100",
                "product_name": "Panel A",
                "product_stage": "量產",
                "supplier_name": "Alpha Electronics",
                "supplier_id": "sup-1",
                "secondary_supplier_name": "Beta Tech",
                "secondary_supplier_id": "sup-2",
                "is_active": True,
            }
        ]
        self._list_suppliers_patch = patch(
            "ui.widgets.master_data_widget._supplier_service.list_suppliers",
            return_value=suppliers,
        )
        self._list_products_patch = patch(
            "ui.widgets.master_data_widget._product_service.list_products",
            return_value=products,
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

    def test_toggle_supplier_cancels_when_confirmation_is_no(self) -> None:
        self.widget._selected_supplier_id = "sup-1"
        with (
            patch(
                "ui.widgets.master_data_supplier_mixin.QMessageBox.question",
                return_value=QMessageBox.StandardButton.No,
            ),
            patch("ui.widgets.master_data_supplier_mixin.event_service.set_supplier_active") as toggle_mock,
        ):
            self.widget._toggle_supplier_active()
        toggle_mock.assert_not_called()

    def test_toggle_product_calls_service_after_confirmation(self) -> None:
        self.widget._selected_product_id = "prd-1"
        with (
            patch(
                "ui.widgets.master_data_product_mixin.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch("ui.widgets.master_data_product_mixin.event_service.set_product_active") as toggle_mock,
            patch("ui.widgets.master_data_product_mixin.QMessageBox.information"),
        ):
            self.widget._toggle_product_active()
        toggle_mock.assert_called_once_with("prd-1", False)

    def test_batch_delete_suppliers_requires_delete_keyword(self) -> None:
        with (
            patch.object(
                self.widget,
                "_selected_table_ids",
                return_value=["sup-1", "sup-2"],
            ),
            patch(
                "ui.widgets.master_data_supplier_mixin.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch(
                "ui.widgets.master_data_supplier_mixin.QInputDialog.getText",
                return_value=("wrong", True),
            ),
            patch("ui.widgets.master_data_supplier_mixin.event_service.delete_suppliers") as delete_mock,
            patch("ui.widgets.master_data_supplier_mixin.QMessageBox.warning") as warning_mock,
        ):
            self.widget._delete_selected_suppliers()
        delete_mock.assert_not_called()
        warning_mock.assert_called()

    def test_batch_delete_suppliers_runs_after_delete_keyword(self) -> None:
        with (
            patch.object(
                self.widget,
                "_selected_table_ids",
                return_value=["sup-1", "sup-2"],
            ),
            patch(
                "ui.widgets.master_data_supplier_mixin.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch(
                "ui.widgets.master_data_supplier_mixin.QInputDialog.getText",
                return_value=("DELETE", True),
            ),
            patch(
                "ui.widgets.master_data_supplier_mixin.event_service.delete_suppliers",
                return_value={"deleted": ["sup-1"], "failed": []},
            ) as delete_mock,
            patch("ui.widgets.master_data_supplier_mixin.QMessageBox.information"),
        ):
            self.widget._delete_selected_suppliers()
        delete_mock.assert_called_once_with(["sup-1", "sup-2"])


if __name__ == "__main__":
    unittest.main()
