from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QTableWidget

from ui.widgets.master_data_widget import ProductFormDialog, ProductStageLogDialog


class MasterDataStageChangeFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


    @classmethod
    def tearDownClass(cls) -> None:
        if cls.app is not None:
            cls.app.quit()

    def _suppliers(self) -> list[dict]:
        return [
            {"id": "sup-1", "supplier_name": "供應商A", "is_active": True},
            {"id": "sup-2", "supplier_name": "供應商B", "is_active": True},
        ]

    def _initial_product(self) -> dict:
        return {
            "id": "prd-1",
            "product_code": "P-001",
            "product_name": "產品A",
            "product_stage": "量產",
            "supplier_id": "sup-1",
            "secondary_supplier_id": "sup-2",
        }

    def test_product_form_downgrade_requires_reason(self) -> None:
        dialog = ProductFormDialog(
            self._suppliers(),
            initial_data=self._initial_product(),
            is_edit=True,
        )
        self.addCleanup(dialog.close)
        dialog.product_stage_combo.setCurrentText("試產")
        with patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes
        ), patch(
            "ui.widgets.master_data_widget.QInputDialog.getMultiLineText",
            return_value=("", True),
        ), patch.object(
            QMessageBox, "warning"
        ) as warning_mock:
            dialog._on_submit()
        self.assertEqual(QDialog.DialogCode.Rejected, dialog.result())
        warning_mock.assert_called()

    def test_product_form_downgrade_accepts_with_reason(self) -> None:
        dialog = ProductFormDialog(
            self._suppliers(),
            initial_data=self._initial_product(),
            is_edit=True,
        )
        self.addCleanup(dialog.close)
        dialog.product_stage_combo.setCurrentText("試產")
        with patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes
        ), patch(
            "ui.widgets.master_data_widget.QInputDialog.getMultiLineText",
            return_value=("客訴回流重開試產", True),
        ):
            dialog._on_submit()
        self.assertEqual(QDialog.DialogCode.Accepted, dialog.result())
        payload = dialog.payload()
        self.assertEqual("客訴回流重開試產", payload["stage_change_reason"])

    def test_stage_log_dialog_renders_rows(self) -> None:
        logs = [
            {
                "changed_at": "2026-04-18 08:00:00",
                "from_stage": "量產",
                "to_stage": "試產",
                "reason": "客訴回流",
                "sync_scope": "all_history_and_future",
                "anomalies_updated": 3,
                "visits_updated": 1,
                "changed_by": "local_user",
            }
        ]
        dialog = ProductStageLogDialog("[P-001] 產品A", logs)
        self.addCleanup(dialog.close)
        table = dialog.findChild(QTableWidget)
        self.assertIsNotNone(table)
        assert table is not None
        self.assertEqual(1, table.rowCount())
        self.assertEqual("客訴回流", table.item(0, 3).text())


if __name__ == "__main__":
    unittest.main()
