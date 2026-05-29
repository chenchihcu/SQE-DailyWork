from __future__ import annotations

import importlib
import unittest
import sys
from types import ModuleType
from unittest.mock import patch

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QApplication, QComboBox, QTableWidgetItem


class AnomalyCategoryDropdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._pandas_patch = patch.dict(sys.modules, {"pandas": ModuleType("pandas")})
        self._pandas_patch.start()
        self.addCleanup(self._pandas_patch.stop)

        sys.modules.pop("ui.widgets.defect_form_widget", None)
        sys.modules.pop("services.event_service", None)
        self.widget_module = importlib.import_module("ui.widgets.defect_form_widget")
        self.NewAnomalyDialog = self.widget_module.NewAnomalyDialog
        self.NewVisitDialog = self.widget_module.NewVisitDialog
        self.category_options = self.widget_module.ANOMALY_CATEGORY_OPTIONS
        self.addCleanup(lambda: sys.modules.pop("ui.widgets.defect_form_widget", None))
        self.addCleanup(lambda: sys.modules.pop("services.event_service", None))

        self._suppliers = [{"id": "sup-1", "supplier_name": "供應商A", "is_active": True}]

        self._patches = [
            patch.object(
                self.widget_module.event_service,
                "preview_anomaly_no",
                return_value="2026年04月16日 -SN 001",
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
                return_value=[],
            ),
            patch.object(
                self.widget_module.event_service,
                "get_latest_visit_for_supplier_on_date",
                return_value=None,
            ),
            patch.object(self.widget_module.QMessageBox, "information"),
            patch.object(self.widget_module.QMessageBox, "warning"),
            patch.object(self.widget_module.QMessageBox, "critical"),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def _select_supplier(self, dialog) -> None:
        idx = dialog.supplier_combo.findData("sup-1")
        self.assertGreaterEqual(idx, 0)
        dialog.supplier_combo.setCurrentIndex(idx)

    def test_category_dropdown_is_editable_and_has_default_options(self) -> None:
        dialog = self.NewAnomalyDialog()
        self.addCleanup(dialog.close)

        self.assertIsInstance(dialog.category_input, QComboBox)
        self.assertTrue(dialog.category_input.isEditable())
        options = [
            dialog.category_input.itemText(i) for i in range(dialog.category_input.count())
        ]
        self.assertEqual(self.category_options, options)

    def test_edit_mode_keeps_custom_category_text(self) -> None:
        dialog = self.NewAnomalyDialog(
            anomaly_id="anomaly-1",
            initial_data={
                "anomaly_no": "2026年04月16日 -SN 001",
                "anomaly_date": "2026-04-16",
                "supplier_id": "sup-1",
                "supplier_name": "供應商A",
                "category": "客製異常A",
            },
        )
        self.addCleanup(dialog.close)

        self.assertEqual("客製異常A", dialog.category_input.currentText())

    def test_submit_payload_uses_dropdown_or_custom_category_text(self) -> None:
        products = [
            {
                "id": "prd-1",
                "product_code": "P-001",
                "product_name": "產品一號",
                "product_stage": "試產",
            }
        ]
        for expected in ("外觀不良", "客製分類-XYZ"):
            captured: dict = {}

            def _fake_create(payload: dict) -> dict:
                captured.update(payload)
                return {"anomaly_no": "2026年04月16日 -SN 001", "visit_action": "none"}

            with self.subTest(category=expected):
                with patch.object(
                    self.widget_module.event_service,
                    "create_anomaly_with_visit_link",
                    side_effect=_fake_create,
                ), patch.object(
                    self.widget_module.event_service,
                    "list_active_products_for_supplier",
                    return_value=products,
                ):
                    dialog = self.NewAnomalyDialog()
                    self.addCleanup(dialog.close)
                    self._select_supplier(dialog)
                    product_idx = dialog.product_combo.findData("prd-1")
                    self.assertGreaterEqual(product_idx, 0)
                    dialog.product_combo.setCurrentIndex(product_idx)
                    dialog.problem_input.setPlainText("測試問題描述")
                    dialog.category_input.setCurrentText(expected)
                    dialog._on_submit()

                self.assertEqual(expected, captured.get("category"))

    def test_anomaly_dialog_product_stage_defaults_to_mass_production(self) -> None:
        dialog = self.NewAnomalyDialog()
        self.addCleanup(dialog.close)
        self.assertEqual("量產", dialog.product_stage_combo.currentText())
        self.assertFalse(dialog.product_stage_combo.isEnabled())

    def test_submit_payload_uses_product_and_keeps_stage_read_only_for_anomaly(self) -> None:
        captured: dict = {}
        products = [
            {
                "id": "prd-1",
                "product_code": "P-001",
                "product_name": "產品一號",
                "product_stage": "試產",
            }
        ]

        def _fake_create(payload: dict) -> dict:
            captured.update(payload)
            return {"anomaly_no": "2026年04月16日 -SN 001", "visit_action": "none"}

        with patch.object(
            self.widget_module.event_service,
            "create_anomaly_with_visit_link",
            side_effect=_fake_create,
        ), patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ):
            dialog = self.NewAnomalyDialog()
            self.addCleanup(dialog.close)
            self._select_supplier(dialog)
            product_idx = dialog.product_combo.findData("prd-1")
            self.assertGreaterEqual(product_idx, 0)
            dialog.product_combo.setCurrentIndex(product_idx)
            self.assertEqual("試產", dialog.product_stage_combo.currentText())
            self.assertFalse(dialog.product_stage_combo.isEnabled())
            dialog.problem_input.setPlainText("測試問題描述")
            dialog._on_submit()

        self.assertEqual("prd-1", captured.get("product_id"))
        self.assertNotIn("product_stage", captured)

    def test_select_product_autofills_stage_for_anomaly_dialog(self) -> None:
        products = [
            {
                "id": "prd-1",
                "product_code": "P-001",
                "product_name": "產品一號",
                "product_stage": "試產",
            }
        ]
        with patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ):
            dialog = self.NewAnomalyDialog()
            self.addCleanup(dialog.close)
            self._select_supplier(dialog)
            product_idx = dialog.product_combo.findData("prd-1")
            self.assertGreaterEqual(product_idx, 0)
            dialog.product_combo.setCurrentIndex(product_idx)
            self.assertEqual("試產", dialog.product_stage_combo.currentText())
            self.assertTrue(dialog.save_button.isEnabled())

    def test_anomaly_dialog_blocks_submit_when_supplier_has_no_products(self) -> None:
        create_spy = patch.object(
            self.widget_module.event_service,
            "create_anomaly_with_visit_link",
            return_value={"anomaly_no": "2026年04月16日 -SN 001", "visit_action": "none"},
        )
        with create_spy as fake_create:
            dialog = self.NewAnomalyDialog()
            self.addCleanup(dialog.close)
            self._select_supplier(dialog)
            self.assertFalse(dialog.save_button.isEnabled())
            dialog.problem_input.setPlainText("測試問題描述")
            dialog._on_submit()
        fake_create.assert_not_called()

    def test_anomaly_dialog_prefills_blank_fields_from_same_day_visit(self) -> None:
        products = [
            {
                "id": "prd-1",
                "product_code": "P-001",
                "product_name": "產品一號",
                "product_stage": "試產",
            }
        ]
        same_day_visit = {
            "id": "visit-1",
            "visit_date": "2026-04-16",
            "supplier_id": "sup-1",
            "product_id": "prd-1",
            "product_name": "產品一號",
            "product_stage": "試產",
            "work_order_no": "WO-200",
            "production_qty": 200,
        }

        with patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ), patch.object(
            self.widget_module.event_service,
            "get_latest_visit_for_supplier_on_date",
            return_value=same_day_visit,
        ):
            dialog = self.NewAnomalyDialog()
            self.addCleanup(dialog.close)
            dialog.date_edit.setDate(QDate(2026, 4, 16))
            self._select_supplier(dialog)

        self.assertEqual("prd-1", dialog.product_combo.currentData())
        self.assertEqual("試產", dialog.product_stage_combo.currentText())
        self.assertEqual("WO-200", dialog.outsource_work_order_input.text())
        self.assertEqual("200", dialog.batch_qty_input.text())
        self.assertEqual(
            "已沿用 2026-04-16 訪廠資料：品名、工單、數量",
            dialog._same_day_visit_hint_label.text(),
        )
        self.assertFalse(dialog._same_day_visit_hint_label.isHidden())

    def test_anomaly_dialog_same_day_prefill_does_not_override_manual_values(self) -> None:
        products = [
            {
                "id": "prd-1",
                "product_code": "P-001",
                "product_name": "產品一號",
                "product_stage": "量產",
            },
            {
                "id": "prd-2",
                "product_code": "P-002",
                "product_name": "產品二號",
                "product_stage": "試產",
            },
        ]

        def _same_day_visit(_supplier_id: str, visit_date: str) -> dict:
            return {
                "id": f"visit-{visit_date}",
                "visit_date": visit_date,
                "supplier_id": "sup-1",
                "product_id": "prd-1",
                "product_name": "產品一號",
                "product_stage": "量產",
                "work_order_no": f"WO-{visit_date}",
                "production_qty": 100,
            }

        with patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ), patch.object(
            self.widget_module.event_service,
            "get_latest_visit_for_supplier_on_date",
            side_effect=_same_day_visit,
        ):
            dialog = self.NewAnomalyDialog()
            self.addCleanup(dialog.close)
            dialog.date_edit.setDate(QDate(2026, 4, 16))
            self._select_supplier(dialog)
            dialog.product_combo.setCurrentIndex(dialog.product_combo.findData("prd-2"))
            dialog.outsource_work_order_input.setText("WO-MANUAL")
            dialog.batch_qty_input.setText("333")

            dialog.date_edit.setDate(QDate(2026, 4, 17))

        self.assertEqual("prd-2", dialog.product_combo.currentData())
        self.assertEqual("試產", dialog.product_stage_combo.currentText())
        self.assertEqual("WO-MANUAL", dialog.outsource_work_order_input.text())
        self.assertEqual("333", dialog.batch_qty_input.text())

    def test_anomaly_edit_mode_does_not_trigger_same_day_prefill(self) -> None:
        with patch.object(
            self.widget_module.event_service,
            "get_latest_visit_for_supplier_on_date",
            return_value={
                "id": "visit-1",
                "visit_date": "2026-04-16",
                "supplier_id": "sup-1",
                "product_id": "prd-1",
                "work_order_no": "WO-200",
                "production_qty": 200,
            },
        ) as latest_visit:
            dialog = self.NewAnomalyDialog(
                anomaly_id="anomaly-1",
                initial_data={
                    "anomaly_no": "20260416001",
                    "anomaly_date": "2026-04-16",
                    "supplier_id": "sup-1",
                    "supplier_name": "供應商A",
                    "product_id": "",
                    "outsource_work_order": "",
                    "batch_qty": 0,
                },
            )
            self.addCleanup(dialog.close)

        latest_visit.assert_not_called()

    def test_visit_dialog_product_stage_defaults_and_submit_payload(self) -> None:
        captured: dict = {}
        products = [
            {
                "id": "prd-2",
                "product_code": "V-001",
                "product_name": "訪廠產品",
                "product_stage": "試產",
            }
        ]

        def _fake_create_visit(payload: dict) -> str:
            captured.update(payload)
            return "visit-001"

        with patch.object(
            self.widget_module.event_service,
            "create_visit",
            side_effect=_fake_create_visit,
        ), patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ):
            dialog = self.NewVisitDialog()
            self.addCleanup(dialog.close)
            self.assertEqual("量產", dialog.product_stage_combo.currentText())
            self.assertFalse(dialog.product_stage_combo.isEnabled())
            self._select_supplier(dialog)
            product_idx = dialog.product_combo.findData("prd-2")
            self.assertGreaterEqual(product_idx, 0)
            dialog.product_combo.setCurrentIndex(product_idx)
            self.assertEqual("試產", dialog.product_stage_combo.currentText())
            self.assertFalse(dialog.product_stage_combo.isEnabled())
            dialog._on_submit()

        self.assertEqual("prd-2", captured.get("product_id"))
        self.assertNotIn("product_stage", captured)
        self.assertEqual("prd-2", captured["product_sections"][0]["product_id"])
        self.assertEqual("試產", captured["product_sections"][0]["product_stage"])
        self.assertFalse(captured.get("tech_transfer", True))
        self.assertFalse(captured.get("tech_transfer_doc", True))
        self.assertFalse(captured.get("carrier_requirement", True))
        self.assertFalse(captured.get("dispensing_process", True))
        self.assertFalse(captured.get("functional_test", True))
        self.assertFalse(captured.get("packaging_requirement", True))

    def test_visit_dialog_focus_defect_note_opens_shared_defect_tab(self) -> None:
        dialog = self.NewVisitDialog(focus_defect_note=True)
        self.addCleanup(dialog.close)

        self.assertEqual("缺失紀錄", dialog.tabs.tabText(dialog.tabs.currentIndex()))
        self.assertEqual(1, dialog.visit_defect_table.rowCount())
        self.assertEqual(0, dialog.visit_defect_table.currentColumn())

    def test_visit_dialog_submits_visit_level_and_product_defect_notes(self) -> None:
        captured: dict = {}
        products = [
            {
                "id": "prd-1",
                "product_code": "P-001",
                "product_name": "產品一號",
                "product_stage": "試產",
            },
            {
                "id": "prd-2",
                "product_code": "P-002",
                "product_name": "產品二號",
                "product_stage": "量產",
            },
        ]

        def _fake_create_visit(payload: dict) -> str:
            captured.update(payload)
            return "visit-001"

        with patch.object(
            self.widget_module.event_service,
            "create_visit",
            side_effect=_fake_create_visit,
        ), patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ):
            dialog = self.NewVisitDialog()
            self.addCleanup(dialog.close)
            self._select_supplier(dialog)
            product_idx = dialog.product_combo.findData("prd-1")
            self.assertGreaterEqual(product_idx, 0)
            dialog.product_combo.setCurrentIndex(product_idx)
            dialog.time_slot_input.setText("上午")
            dialog.work_order_input.setText("WO-A")
            dialog.primary_defect_table.add_empty_note()
            dialog.primary_defect_table.setItem(0, 0, QTableWidgetItem("材料未全檢"))
            dialog.primary_defect_table.setItem(0, 1, QTableWidgetItem("已建立 SOP"))
            dialog.visit_defect_table.add_empty_note()
            dialog.visit_defect_table.setItem(0, 0, QTableWidgetItem("共通現場問題"))

            extra = dialog._add_extra_product_section()
            extra.product_combo.setCurrentIndex(extra.product_combo.findData("prd-2"))
            extra.time_slot_input.setText("下午")
            extra.defect_table.add_empty_note()
            extra.defect_table.setItem(0, 0, QTableWidgetItem("規格書未收到"))
            extra.defect_table.setItem(0, 2, QTableWidgetItem("下次補看"))
            dialog._on_submit()

        self.assertEqual("共通現場問題", captured["defect_notes"][0]["defect_desc"])
        self.assertEqual(2, len(captured["product_sections"]))
        self.assertEqual("prd-1", captured["product_sections"][0]["product_id"])
        self.assertEqual("上午", captured["product_sections"][0]["time_slot"])
        self.assertEqual("材料未全檢", captured["product_sections"][0]["defect_notes"][0]["defect_desc"])
        self.assertEqual("prd-2", captured["product_sections"][1]["product_id"])
        self.assertEqual("下午", captured["product_sections"][1]["time_slot"])
        self.assertEqual("", captured["product_sections"][1]["defect_notes"][0]["improvement_desc"])

    def test_visit_dialog_item_yes_auto_checks_tech_transfer(self) -> None:
        captured: dict = {}
        products = [
            {
                "id": "prd-2",
                "product_code": "V-001",
                "product_name": "訪廠產品",
                "product_stage": "試產",
            }
        ]

        def _fake_create_visit(payload: dict) -> str:
            captured.update(payload)
            return "visit-001"

        with patch.object(
            self.widget_module.event_service,
            "create_visit",
            side_effect=_fake_create_visit,
        ), patch.object(
            self.widget_module.event_service,
            "list_active_products_for_supplier",
            return_value=products,
        ):
            dialog = self.NewVisitDialog()
            self.addCleanup(dialog.close)
            self._select_supplier(dialog)
            product_idx = dialog.product_combo.findData("prd-2")
            self.assertGreaterEqual(product_idx, 0)
            dialog.product_combo.setCurrentIndex(product_idx)
            functional_group = dialog._tech_transfer_groups["functional_test"]
            yes_button = functional_group.button(1)
            self.assertIsNotNone(yes_button)
            assert yes_button is not None
            yes_button.setChecked(True)
            self.assertTrue(dialog.tech_transfer_check.isChecked())
            dialog._on_submit()

        self.assertTrue(captured.get("tech_transfer"))
        self.assertTrue(captured.get("functional_test"))

    def test_uncheck_tech_transfer_resets_all_items_to_no(self) -> None:
        dialog = self.NewVisitDialog()
        self.addCleanup(dialog.close)
        self._select_supplier(dialog)

        for field_key in ("tech_transfer_doc", "carrier_requirement"):
            group = dialog._tech_transfer_groups[field_key]
            yes_button = group.button(1)
            self.assertIsNotNone(yes_button)
            assert yes_button is not None
            yes_button.setChecked(True)

        self.assertTrue(dialog.tech_transfer_check.isChecked())
        dialog.tech_transfer_check.setChecked(False)
        self.assertFalse(dialog.tech_transfer_check.isChecked())
        for key, _label in self.widget_module.VISIT_TECH_TRANSFER_ITEMS:
            self.assertFalse(dialog._get_tech_transfer_item(key))

    def test_visit_dialog_edit_mode_applies_item_flags(self) -> None:
        dialog = self.NewVisitDialog(
            visit_id="visit-1",
            initial_data={
                "visit_date": "2026-04-16",
                "supplier_id": "sup-1",
                "supplier_name": "供應商A",
                "tech_transfer": False,
                "functional_test": True,
                "carrier_requirement": False,
                "tech_transfer_doc": False,
                "dispensing_process": False,
                "packaging_requirement": False,
            },
        )
        self.addCleanup(dialog.close)

        self.assertTrue(dialog.tech_transfer_check.isChecked())
        self.assertTrue(dialog._get_tech_transfer_item("functional_test"))
        self.assertFalse(dialog._get_tech_transfer_item("carrier_requirement"))

    def test_visit_dialog_tech_transfer_cards_use_right_side_dot_indicator_style(self) -> None:
        dialog = self.NewVisitDialog()
        self.addCleanup(dialog.close)
        self._select_supplier(dialog)

        for field_key, _label in self.widget_module.VISIT_TECH_TRANSFER_ITEMS:
            card = dialog._tech_transfer_cards[field_key]
            self.assertEqual(Qt.LayoutDirection.RightToLeft, card.yes_radio.layoutDirection())
            self.assertEqual(Qt.LayoutDirection.RightToLeft, card.no_radio.layoutDirection())

        # Style is now handled globally via 'techTransferCard' objectName and properties.
        # We only verify the layout direction which determines the right-side positioning.


if __name__ == "__main__":
    unittest.main()
