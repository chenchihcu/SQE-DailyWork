from __future__ import annotations

import importlib
import sys
import unittest
from types import ModuleType
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from services.anomaly_trace_contract import ANOMALY_SOURCE_OTHER

import services.event._anomaly_service as _anomaly_service_mod


class AnomalyProcessKeywordsFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._pandas_patch = patch.dict(sys.modules, {"pandas": ModuleType("pandas")})
        self._pandas_patch.start()
        self.addCleanup(self._pandas_patch.stop)

        sys.modules.pop("ui.widgets.defect_form_shim", None)
        self.widget_module = importlib.import_module("ui.widgets.defect_form_shim")
        self.addCleanup(lambda: sys.modules.pop("ui.widgets.defect_form_shim", None))

        import services.event_service as canonical_event_service

        self.widget_module.event_service = canonical_event_service
        self.NewAnomalyDialog = self.widget_module.NewAnomalyDialog

        self._suppliers = [{"id": "sup-1", "supplier_name": "供應商A", "is_active": True}]
        self._products = [
            {
                "id": "prd-1",
                "product_code": "P-001",
                "product_name": "產品一號",
                "product_stage": "量產",
            }
        ]

        self._patches = [
            patch.object(
                self.widget_module.event_service,
                "preview_anomaly_no",
                side_effect=lambda d: d.replace("-", "") + "001" if d else "20260702001",
            ),
            patch.object(
                _anomaly_service_mod,
                "preview_anomaly_no",
                side_effect=lambda d: d.replace("-", "") + "001" if d else "20260702001",
            ),
            patch.object(
                self.widget_module.event_service,
                "list_active_suppliers",
                return_value=self._suppliers,
            ),
            patch.object(
                self.widget_module.event_service,
                "list_suppliers",
                return_value=self._suppliers,
            ),
            patch.object(
                self.widget_module.event_service,
                "list_active_products_for_supplier",
                return_value=self._products,
            ),
            patch.object(
                _anomaly_service_mod,
                "get_latest_visit_for_supplier_on_date",
                return_value=None,
            ),
            patch.object(self.widget_module.QMessageBox, "information"),
            patch.object(self.widget_module.QMessageBox, "warning"),
            patch.object(self.widget_module.QMessageBox, "critical"),
        ]
        for item in self._patches:
            item.start()
            self.addCleanup(item.stop)

    def test_edit_mode_loads_process_keywords(self) -> None:
        dialog = self.NewAnomalyDialog(
            anomaly_id="anomaly-1",
            initial_data={
                "anomaly_no": "20260416001",
                "anomaly_date": "2026-04-16",
                "supplier_id": "sup-1",
                "supplier_name": "供應商A",
                "process_keywords": "SPI\n回流焊",
            },
        )
        self.addCleanup(dialog.close)

        self.assertEqual(["SPI", "回流焊"], dialog.process_keywords_input.tags())

    def test_submit_payload_includes_process_keywords(self) -> None:
        captured: dict = {}
        products = self._products

        def _fake_create(payload: dict) -> dict:
            captured.update(payload)
            return {
                "anomaly_no": "20260416001",
                "anomaly_id": "new-anomaly",
                "visit_action": "none",
                "warnings": [],
            }

        with patch.object(
            self.widget_module.event_service,
            "create_anomaly_with_visit_link",
            side_effect=_fake_create,
        ), patch.object(
            _anomaly_service_mod,
            "create_anomaly_with_visit_link",
            side_effect=_fake_create,
        ), patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ):
            dialog = self.NewAnomalyDialog()
            self.addCleanup(dialog.close)
            dialog.supplier_combo.setCurrentIndex(
                max(dialog.supplier_combo.findData("sup-1"), 0)
            )
            product_idx = dialog.product_combo.findData("prd-1")
            self.assertGreaterEqual(product_idx, 0)
            dialog.product_combo.setCurrentIndex(product_idx)
            dialog.problem_input.set_formatted_text("1. 錫膏印刷異常")
            dialog.quality_report_no_radio.setChecked(True)
            dialog.anomaly_source_combo.setCurrentText(ANOMALY_SOURCE_OTHER)
            dialog.process_keywords_input.set_delimited_text("SPI\n空焊")
            dialog._on_submit()

        self.assertEqual("SPI\n空焊", captured.get("process_keywords"))


if __name__ == "__main__":
    unittest.main()
